from datetime import datetime
from typing import Dict, List, Any, Optional

from src.config import (
    STATUS_AFFORDABLE_NOW, STATUS_AFFORDABLE_WITH_PLAN,
    STATUS_AFFORDABLE_LATER, STATUS_NOT_AFFORDABLE,
    METHOD_FULL_PAYMENT, METHOD_PARTIAL_PAYMENT,
    METHOD_INSTALLMENTS, METHOD_WAIT, METHOD_NOT_RECOMMENDED
)
from src.data_loader import DataLoader

def format_date_natural(dt_str: str) -> str:
    if not dt_str:
        return ""
    dt = datetime.strptime(dt_str, "%Y-%m-%d")
    return f"{dt.day} {dt.strftime('%B %Y')}"

def format_currency_amount(amount: float) -> str:
    if abs(amount - round(amount)) < 1e-4:
        return f"{int(round(amount)):,}"
    else:
        return f"{amount:,.2f}"

class Explainer:
    def __init__(self, data_loader: DataLoader):
        self.dl = data_loader

    def generate_explanation(self, request: Dict[str, Any], plan_result: Dict[str, Any]) -> str:
        req_id = request['request_id']
        u_id = request['user_id']
        profile = self.dl.profiles[u_id]
        curr = profile['home_currency']
        min_bal = profile['minimum_balance_to_keep']
        min_bal_fmt = format_currency_amount(min_bal)

        req_amt = request['requested_amount']
        req_amt_fmt = format_currency_amount(req_amt)
        req_date = request['request_date']
        desired_date = request['desired_completion_date']
        desired_date_nat = format_date_natural(desired_date)

        safe_today = plan_result['amount_safe_to_pay']
        safe_amt_fmt = format_currency_amount(safe_today)

        status = plan_result['affordability_status']
        method = plan_result['recommended_payment_method']
        earliest_full = plan_result.get('earliest_date_for_full_payment', '')
        earliest_full_nat = format_date_natural(earliest_full) if earliest_full else ""
        spending_changes = plan_result.get('spending_changes_needed', 'none')

        # 1. Affordable Now / Full Payment without spending changes
        if status == STATUS_AFFORDABLE_NOW and method == METHOD_FULL_PAYMENT:
            return f"Pay {curr} {req_amt_fmt} today. This leaves at least {curr} {min_bal_fmt} available over the next 90 days."

        # 2. Affordable with Plan: Full Payment with Spending Changes
        if status == STATUS_AFFORDABLE_WITH_PLAN and method == METHOD_FULL_PAYMENT:
            actions_text = self._build_spending_actions_text(spending_changes, curr)
            return f"{actions_text}, then pay {curr} {req_amt_fmt} today. This leaves at least {curr} {min_bal_fmt} available."

        # 3. Affordable with Plan: Partial Payment
        if status == STATUS_AFFORDABLE_WITH_PLAN and method == METHOD_PARTIAL_PAYMENT:
            rem_amt = round(req_amt - safe_today, 2)
            rem_amt_fmt = format_currency_amount(rem_amt)
            return f"Pay {curr} {safe_amt_fmt} today and the remaining {curr} {rem_amt_fmt} on {earliest_full_nat}. This completes the full request and keeps the {curr} {min_bal_fmt} minimum protected."

        # 4. Affordable with Plan: Installments
        if status == STATUS_AFFORDABLE_WITH_PLAN and method == METHOD_INSTALLMENTS:
            opt = plan_result.get('selected_option')
            if opt:
                num_pmts = opt['number_of_payments']
                pmt_amt_fmt = format_currency_amount(opt['payment_amount'])
                first_date_nat = format_date_natural(opt['first_payment_date'])
            else:
                plan_parts = plan_result['payment_plan'].split('|')
                num_pmts = len(plan_parts)
                first_date_nat = format_date_natural(plan_parts[0].split(':')[0])
                pmt_amt_fmt = format_currency_amount(float(plan_parts[0].split(':')[1]))

            return f"Use {num_pmts} installments of {curr} {pmt_amt_fmt}, starting {first_date_nat}. This leaves at least {curr} {min_bal_fmt} available."

        # 5. Affordable Later: Wait
        if status == STATUS_AFFORDABLE_LATER and method == METHOD_WAIT:
            return f"Pay {curr} {req_amt_fmt} in full on {earliest_full_nat}. Paying earlier would take the balance below the {curr} {min_bal_fmt} minimum."

        # 6. Not Affordable / Not Recommended
        if status == STATUS_NOT_AFFORDABLE or method == METHOD_NOT_RECOMMENDED:
            considered = profile['payment_methods_user_will_consider']
            if considered == ['partial_payment'] and request['allows_partial_payment'] and safe_today > 0:
                return f"Do not proceed with the {curr} {req_amt_fmt} request. Although {curr} {safe_amt_fmt} is available today, the full amount cannot be completed safely within 90 days."
            else:
                return f"Do not make this payment by {desired_date_nat}. None of the available options keeps the {curr} {min_bal_fmt} minimum protected."

        return f"Do not make this payment by {desired_date_nat}. None of the available options keeps the {curr} {min_bal_fmt} minimum protected."

    def _build_spending_actions_text(self, changes_str: str, curr: str) -> str:
        if not changes_str or changes_str == 'none':
            return ""

        parts = changes_str.split('|')
        phrases = []
        for p in parts:
            if p.startswith('stop:'):
                e_id = p.split(':')[1]
                desc = self.dl.events.get(e_id, {}).get('description', 'expense').lower()
                phrases.append(f"stop the {desc}")
            elif p.startswith('reduce_to:'):
                seg = p.split(':')
                e_id = seg[1]
                new_val = float(seg[2])
                new_val_fmt = format_currency_amount(new_val)
                desc = self.dl.events.get(e_id, {}).get('description', 'expense').lower()
                phrases.append(f"reduce the {desc} to {curr} {new_val_fmt}")

        if not phrases:
            return ""

        phrases[0] = phrases[0][0].upper() + phrases[0][1:]

        if len(phrases) == 1:
            return phrases[0]
        elif len(phrases) == 2:
            return f"{phrases[0]} and {phrases[1]}"
        else:
            return f"{phrases[0]}, {phrases[1]}, and {phrases[2]}"
