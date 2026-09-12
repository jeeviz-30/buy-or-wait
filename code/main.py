import argparse
import csv
import sys
import os
from pathlib import Path

# Add code directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.data_loader import DataLoader
from src.message_parser import MessageParser
from src.forecaster import Forecaster
from src.solvers import Solvers
from src.plan_selector import PlanSelector
from src.explainer import Explainer
from src.telemetry import TelemetryTracker

def main():
    parser = argparse.ArgumentParser(description="HackerRank Orchestrate: Buy or Wait? AI Financial Decision Agent")
    parser.add_argument("--dataset-dir", default="dataset", help="Path to dataset directory")
    parser.add_argument("--output", default="output.csv", help="Path to write output predictions CSV")
    args = parser.parse_args()

    dataset_path = Path(args.dataset_dir)
    output_path = Path(args.output)

    print(f"============================================================")
    print(f"HackerRank Orchestrate — Buy or Wait? Financial Decision Agent")
    print(f"Dataset directory : {dataset_path.resolve()}")
    print(f"Output CSV path   : {output_path.resolve()}")
    print(f"============================================================")

    # Initialize Telemetry
    telemetry = TelemetryTracker()

    # Load all datasets and multimodal evidence
    print("\n[1/4] Loading financial profiles, historical events, messages, and receipt data...")
    dl = DataLoader(dataset_path)
    mp = MessageParser(dl.messages_by_user)
    fc = Forecaster(dl, mp)
    solvers = Solvers(dl, fc)
    plan_selector = PlanSelector(dl, solvers)
    explainer = Explainer(dl)
    print(f"Loaded {len(dl.profiles)} profiles, {len(dl.events)} events, {len(dl.payment_options)} payment option sets.")

    # Load evaluation requests
    requests_file = dataset_path / "requests.csv"
    if not requests_file.exists():
        print(f"ERROR: Requests file not found at {requests_file}")
        sys.exit(1)

    requests = []
    with open(requests_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            requests.append(row)

    print(f"\n[2/4] Processing {len(requests)} evaluation requests...")

    output_rows = []
    for i, req in enumerate(requests, 1):
        telemetry.record_request()
        
        req_dict = {
            'request_id': req['request_id'],
            'user_id': req['user_id'],
            'request_date': req['request_date'],
            'request_type': req['request_type'],
            'requested_amount': float(req['requested_amount']),
            'desired_completion_date': req['desired_completion_date'],
            'allows_partial_payment': req['allows_partial_payment'].lower() == 'true',
            'request_text': req['request_text']
        }

        # Solve optimal plan
        plan_result = plan_selector.evaluate_request(req_dict)
        
        # Generate grounded explanation
        explanation = explainer.generate_explanation(req_dict, plan_result)

        # Format amount_safe_to_pay: integer if integer, else float
        safe_amt = plan_result['amount_safe_to_pay']
        if abs(safe_amt - round(safe_amt)) < 1e-4:
            safe_amt_str = str(int(round(safe_amt)))
        else:
            safe_amt_str = f"{safe_amt:.2f}".rstrip('0').rstrip('.') if '.' in f"{safe_amt:.2f}" else f"{safe_amt:.2f}"

        row_dict = {
            'request_id': req['request_id'],
            'amount_safe_to_pay': safe_amt_str,
            'affordability_status': plan_result['affordability_status'],
            'recommended_payment_method': plan_result['recommended_payment_method'],
            'payment_plan': plan_result['payment_plan'],
            'earliest_date_for_full_payment': plan_result['earliest_date_for_full_payment'],
            'spending_changes_needed': plan_result['spending_changes_needed'],
            'decision_explanation': explanation
        }
        output_rows.append(row_dict)

        if i % 50 == 0 or i == len(requests):
            print(f"  Processed {i}/{len(requests)} requests ({i/len(requests)*100:.1f}%)")

    # Write output.csv
    print(f"\n[3/4] Writing predictions to {output_path}...")
    fieldnames = [
        'request_id',
        'amount_safe_to_pay',
        'affordability_status',
        'recommended_payment_method',
        'payment_plan',
        'earliest_date_for_full_payment',
        'spending_changes_needed',
        'decision_explanation'
    ]

    # Save to requested output path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    # Also save to dataset/output.csv and root output.csv for safety
    repo_root = Path(__file__).resolve().parent.parent
    for dest in [repo_root / "output.csv", dataset_path / "output.csv"]:
        if dest != output_path.resolve():
            with open(dest, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(output_rows)

    # Generate telemetry report
    print("\n[4/4] Generating usage and cost report...")
    report_paths = [
        repo_root / "evaluation" / "usage_report.md",
        repo_root / "code" / "evaluation" / "usage_report.md"
    ]
    telemetry.generate_report(report_paths)

    print("\n============================================================")
    print("SUCCESS: Execution completed cleanly!")
    print(f"Total evaluated requests: {len(output_rows)}")
    print(f"Output files verified   : {output_path}")
    print("============================================================")

if __name__ == "__main__":
    main()
