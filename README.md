# Customer Support AI Evaluation Pipeline

A replayable, staged Python pipeline designed to ingest customer support tickets, generate AI-drafted replies using Google Gemini, and rigorously evaluate those replies using a combination of deterministic Python checks and structured LLM quality reviews.

The pipeline ensures safety and quality by gating outputs behind an interactive human-in-the-loop override checkpoint before generating a final Markdown evaluation report and a strict artifact validation script.

## 🚀 Features
- **Generative AI Drafting**: Uses `gemini-2.5-flash` to automatically draft context-aware support replies.
- **Deterministic Check Engine**: Pure Python heuristic checking enforcing policy compliance (e.g. banning password requests or unauthorized funds release promises).
- **Structured LLM Review**: A secondary LLM agent grades the draft out of 5, assesses risk levels, and provides actionable improvement suggestions via JSON schema output.
- **Interactive Checkpoint**: Blocks final routing decisions until a human operator has a chance to manually override routes in the terminal.
- **Headless CI Support**: Provides a `--ci` flag for fully automated, headless execution.
- **Full Audit Logging**: Maintains a `llm_calls.jsonl` log recording prompt SHA-256 hashes, timestamps, and artifacts used for every LLM interaction.

## 🛠️ Setup Instructions

1. **Install Dependencies**
   Ensure you have Python 3.11+ installed. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**
   Copy the example environment file and add your Google Gemini API key:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and set `GEMINI_API_KEY=your_actual_api_key_here`.

## 💻 How to Run

### Interactive Run (Human-in-the-Loop)
To run the standard pipeline, execute the main module from the project root:
```bash
python -m src.pipeline
```
During this run, the terminal will pause and prompt you to enter overrides (e.g., `TKT-001 human_review`). Press `Enter` on an empty line to finish and resume.

### CI/CD Mode (Headless)
To run the pipeline fully automated without waiting for human input:
```bash
python -m src.pipeline --ci
```

### Advanced Flags
- `--tickets path/to/tickets.json` : Override the default input tickets file.
- `--policy path/to/policy.json` : Override the default input policy file.

## 📂 Output Artifacts
All artifacts generated during execution are saved in the `outputs/` directory:

- `normalized_tickets.json`: Cleaned up and timestamped ticket data.
- `draft_replies.json`: The generated AI responses for each ticket.
- `policy_checks.json`: Deterministic scoring metrics and pass/fail flags.
- `llm_review.json`: Quality grading (1-5) and risk assessments from the Review agent.
- `human_overrides.json`: A record of any manual route changes applied during execution.
- `final_decisions.json`: The ultimate resolved route and reasoning for every ticket.
- `evaluation_report.md`: A dynamically generated summary report with QA suggestions.
- `llm_calls.jsonl`: Append-only audit logs tracking every Gemini API call.

## 🧪 Validation
At the end of every successful run, the pipeline automatically executes `validate.py`. This script performs a 10-point checklist verifying that all artifacts exist, JSON schemas are valid, LLM calls did not overlap, and business logic routing equations were satisfied correctly.
