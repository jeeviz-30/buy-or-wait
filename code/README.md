# Buy or Wait? — AI Financial Decision Agent
**HackerRank Orchestrate (September 2026)**

An autonomous, multimodal financial decision agent that evaluates user expense requests and decides whether the user should pay in full today, pay partially, use installments, wait, or not proceed.

---

## 1. System Architecture

The solution uses a hybrid neuro-symbolic financial architecture:

1. **Multimodal Evidence Ingestion (`src/data_loader.py`)**:
   - Parses `images.csv` and `media/images/` to extract exact receipts and invoice totals for all 16 financial events with blank amounts (`event_253`, `event_1442`, etc.).
   - Parses fixed dated exchange rates from `exchange_rates.csv` to convert foreign-currency cash events into the user's `home_currency`.

2. **Context & Policy Parser (`src/message_parser.py`)**:
   - Extracts semantic updates from untrusted user/employer messages: salary date changes, arrears, rent increases, seasonal contract terminations, and confirmed invoices while filtering prompt injection attempts.

3. **90-Day Cash Flow Simulation Engine (`src/forecaster.py`)**:
   - Reconstructs cash trajectories across a 90-day conservative horizon.
   - Detects periodic expense recurrences (monthly bills like rent/utilities and variable intervals like groceries, transport, and dining).
   - Counts confirmed salaries on their settlement dates, accounting for seasonal contracts, arrears, and mode settlement schedules.

4. **Constraint Solver & Plan Optimizer (`src/solvers.py`, `src/plan_selector.py`)**:
   - Determines `amount_safe_to_pay` as the maximum immediate safe expenditure that preserves `minimum_balance_to_keep` throughout the forecast.
   - Computes `earliest_date_for_full_payment` independent of payment preferences.
   - Evaluates eligible payment plans (`full_payment`, `partial_payment`, `installments`, `wait`) and applies the strict 6-tier tie-breaking ranking:
     1. Completion by `desired_completion_date`
     2. Minimization of spending changes (0 changes preferred)
     3. Minimization of total amount paid
     4. Earlier start date
     5. Fewer payment installments
     6. Lowest `payment_option_id`
   - Formulates minimal, targeted spending change actions (`stop:<event_id>` and `reduce_to:<event_id>:<new_amount>`) targeting non-protected, flexible categories.

5. **Grounded Decision Explainer (`src/explainer.py`)**:
   - Synthesizes transparent, human-readable explanations strictly grounded in financial data and user minimum balance constraints.

6. **Telemetry & Audit Tracking (`src/telemetry.py`)**:
   - Tracks model calls, token consumption, and compute costs, generating `evaluation/usage_report.md`.

---

## 2. Setup & Execution

### Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Standard library dependencies (`csv`, `datetime`, `collections`, `pathlib`, `argparse`)
- Pillow (`pip install pillow`) for image verification

### Run Full Prediction Pipeline
To evaluate `dataset/requests.csv` and generate `output.csv`:

```bash
python code/main.py --dataset-dir dataset --output output.csv
```

The script will:
- Process all 250 evaluation requests.
- Produce `output.csv` matching the exact column order and contract specifications.
- Generate `evaluation/usage_report.md`.

---

## 3. Submission Package
- `output.csv`: Full evaluation predictions for all 250 requests.
- `code.zip`: Contains the full runnable codebase (`code/`), `README.md`, and `evaluation/usage_report.md`.
- Submission URL: https://www.hackerrank.com/contests/hackerrank-orchestrate-september26/challenges/buy-or-wait/submission
