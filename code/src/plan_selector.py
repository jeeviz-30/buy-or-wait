from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

from src.config import (
    STATUS_AFFORDABLE_NOW, STATUS_AFFORDABLE_WITH_PLAN,
    STATUS_AFFORDABLE_LATER, STATUS_NOT_AFFORDABLE,
    METHOD_FULL_PAYMENT, METHOD_PARTIAL_PAYMENT,
    METHOD_INSTALLMENTS, METHOD_WAIT, METHOD_NOT_RECOMMENDED
)
from src.solvers import Solvers
from src.data_loader import DataLoader

class PlanSelector:
    def __init__(self, data_loader: DataLoader, solvers: Solvers):
        self.dl = data_loader
        self.solvers = solvers

    def evaluate_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        req_id = request['request_id']
        u_id = request['user_id']
        req_date = request['request_date']
        req_amt = request['requested_amount']
        desired_date = request['desired_completion_date']
        allows_partial = request['allows_partial_payment']

        profile = self.dl.profiles[u_id]
        considered_methods = profile['payment_methods_user_will_consider']
        max_months = profile['max_installment_months']

        # 1. Amount safe to pay today
        safe_today = self.solvers.calculate_amount_safe_to_pay(u_id, req_date, req_amt)

        # 2. Earliest date for full payment
        earliest_full_date = self.solvers.find_earliest_date_for_full_payment(u_id, req_date, req_amt)

        # 3. Generate candidate safe plans
        candidates = []

        # Candidate A: Full Payment
        if METHOD_FULL_PAYMENT in considered_methods:
            is_safe, changes = self.solvers.find_spending_changes_for_plan(u_id, req_date, [(req_date, req_amt)])
            if is_safe:
                plan_str = f"{req_date}:{self._fmt_amt(req_amt)}"
                candidates.append({
                    'method': METHOD_FULL_PAYMENT,
                    'option_id': 'option_00_full',
                    'payments': [(req_date, req_amt)],
                    'plan_str': plan_str,
                    'completion_date': req_date,
                    'start_date': req_date,
                    'spending_changes': changes,
                    'num_changes': len(changes),
                    'total_paid': req_amt,
                    'num_payments': 1,
                    'completes_by_deadline': req_date <= desired_date,
                    'selected_option': None
                })

        # Candidate B: Partial Payment
        if allows_partial and (METHOD_PARTIAL_PAYMENT in considered_methods):
            if 0 < safe_today < req_amt and earliest_full_date and earliest_full_date <= desired_date:
                remainder = round(req_amt - safe_today, 2)
                partial_payments = [(req_date, safe_today), (earliest_full_date, remainder)]
                is_safe, changes = self.solvers.find_spending_changes_for_plan(u_id, req_date, partial_payments)
                if is_safe and len(changes) == 0:
                    plan_str = f"{req_date}:{self._fmt_amt(safe_today)}|{earliest_full_date}:{self._fmt_amt(remainder)}"
                    candidates.append({
                        'method': METHOD_PARTIAL_PAYMENT,
                        'option_id': 'option_00_partial',
                        'payments': partial_payments,
                        'plan_str': plan_str,
                        'completion_date': earliest_full_date,
                        'start_date': req_date,
                        'spending_changes': [],
                        'num_changes': 0,
                        'total_paid': req_amt,
                        'num_payments': 2,
                        'completes_by_deadline': True,
                        'selected_option': None
                    })

        # Candidate C: Installments
        if METHOD_INSTALLMENTS in considered_methods:
            options = self.dl.payment_options.get(req_id, [])
            for opt in options:
                num_payments = opt['number_of_payments']
                freq_days = opt['payment_frequency_days'] or 30
                total_span_days = (num_payments - 1) * freq_days
                total_months = round(total_span_days / 30.0)
                if max_months is not None and total_months > max_months:
                    continue

                first_dt = datetime.strptime(opt['first_payment_date'], '%Y-%m-%d')
                pmt_amt = opt['payment_amount']
                payments = []
                for i in range(num_payments):
                    p_dt = first_dt + timedelta(days=i * freq_days)
                    payments.append((p_dt.strftime('%Y-%m-%d'), pmt_amt))
                
                last_dt_str = payments[-1][0]
                is_safe, changes = self.solvers.find_spending_changes_for_plan(u_id, req_date, payments)
                if is_safe:
                    plan_str = "|".join(f"{d}:{self._fmt_amt(a)}" for d, a in payments)
                    candidates.append({
                        'method': METHOD_INSTALLMENTS,
                        'option_id': opt['payment_option_id'],
                        'payments': payments,
                        'plan_str': plan_str,
                        'completion_date': last_dt_str,
                        'start_date': opt['first_payment_date'],
                        'spending_changes': changes,
                        'num_changes': len(changes),
                        'total_paid': opt['total_payable_amount'],
                        'num_payments': num_payments,
                        'completes_by_deadline': last_dt_str <= desired_date,
                        'selected_option': opt
                    })

        # Candidate D: Wait
        if METHOD_FULL_PAYMENT in considered_methods and earliest_full_date:
            if earliest_full_date > req_date and earliest_full_date <= desired_date:
                plan_str = f"{earliest_full_date}:{self._fmt_amt(req_amt)}"
                candidates.append({
                    'method': METHOD_WAIT,
                    'option_id': 'option_99_wait',
                    'payments': [(earliest_full_date, req_amt)],
                    'plan_str': plan_str,
                    'completion_date': earliest_full_date,
                    'start_date': earliest_full_date,
                    'spending_changes': [],
                    'num_changes': 0,
                    'total_paid': req_amt,
                    'num_payments': 1,
                    'completes_by_deadline': True,
                    'selected_option': None
                })

        # Rank candidates
        def rank_key(c):
            return (
                0 if c['completes_by_deadline'] else 1,
                c['num_changes'],
                c['total_paid'],
                c['start_date'],
                c['num_payments'],
                c['option_id']
            )

        candidates.sort(key=rank_key)

        # Select best plan
        if candidates and candidates[0]['completes_by_deadline']:
            best = candidates[0]
            rec_method = best['method']
            plan_str = best['plan_str']
            changes = best['spending_changes']
            changes_str = "|".join(changes) if changes else 'none'
            selected_option = best.get('selected_option')

            if rec_method == METHOD_FULL_PAYMENT:
                if len(changes) == 0 and req_date == earliest_full_date:
                    aff_status = STATUS_AFFORDABLE_NOW
                else:
                    aff_status = STATUS_AFFORDABLE_WITH_PLAN
            elif rec_method in (METHOD_PARTIAL_PAYMENT, METHOD_INSTALLMENTS):
                aff_status = STATUS_AFFORDABLE_WITH_PLAN
            elif rec_method == METHOD_WAIT:
                aff_status = STATUS_AFFORDABLE_LATER
            else:
                aff_status = STATUS_NOT_AFFORDABLE
        else:
            rec_method = METHOD_NOT_RECOMMENDED
            plan_str = 'none'
            changes_str = 'none'
            aff_status = STATUS_NOT_AFFORDABLE
            selected_option = None

        return {
            'request_id': req_id,
            'amount_safe_to_pay': safe_today,
            'affordability_status': aff_status,
            'recommended_payment_method': rec_method,
            'payment_plan': plan_str,
            'earliest_date_for_full_payment': earliest_full_date if aff_status != STATUS_NOT_AFFORDABLE else "",
            'spending_changes_needed': changes_str,
            'selected_option': selected_option
        }

    def _fmt_amt(self, val: float) -> str:
        if abs(val - round(val)) < 1e-4:
            return str(int(round(val)))
        return f"{val:.2f}" 
