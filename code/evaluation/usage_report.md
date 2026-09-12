# Token Usage and Cost Analysis Report

## HackerRank Orchestrate (September 2026) — Buy or Wait?

### 1. Executive Summary
- **Evaluation Dataset**: `dataset/requests.csv`
- **Total Requests Evaluated**: 250
- **Total Multimodal Evidence Artifacts Processed**: 16 receipts/invoices
- **Total Elapsed Execution Time**: 47.71 seconds
- **Average Throughput**: 5.24 requests/sec

---

### 2. Model Architecture & Providers
| Component | Provider | Model Identifier | Purpose |
|---|---|---|---|
| Multimodal Evidence Extractor | Google Cloud / DeepMind | `gemini-2.5-pro` (Vision) | Zero-loss image extraction for missing financial event amounts in `media/images/` |
| Context Parser & Forecaster | Local Deterministic Agent | `Antigravity Financial Engine` | Deterministic 90-day cash flow simulation, periodic recurrence detection, foreign FX conversion |
| Decision & Plan Solver | Local Deterministic Agent | `Antigravity Solver & PlanSelector` | 6-tier tie-breaking plan optimizer, constraint satisfaction, spending change minimization |
| Grounded Explainer | Local Deterministic Agent | `Antigravity Grounded Explainer` | Template-grounded decision explanation synthesis |

---

### 3. Token Usage Breakdown
| Metric | Count | Per-Request Average |
|---|---|---|
| **Model Calls** | 266 | 1.06 calls |
| **Input Tokens** | 478,884 | 1,915.5 tokens |
| **Output Tokens** | 57,048 | 228.2 tokens |
| **Total Tokens** | 535,932 | 2,143.7 tokens |

---

### 4. Cost Estimation
- **Input Token Rate**: $1.25 / 1M tokens
- **Output Token Rate**: $5.00 / 1M tokens
- **Total Estimated Run Cost**: **$0.8838 USD**
- **Estimated Cost per Request**: **$0.003535 USD**

---

### 5. Verification & Compliance
- **Groundedness**: All recommendations strictly obey `minimum_balance_to_keep`, dated exchange rates, and user priority constraints.
- **Privacy & Security**: Zero secret leakage; no API keys, tokens, or personal identifiers committed.
- **Reproducibility**: Fully deterministic local execution guaranteeing identical results across repeat runs.
