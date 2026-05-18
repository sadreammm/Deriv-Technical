"""
Utility: Append-only JSONL logger for every LLM call.
"""

import json
import os
from datetime import datetime, timezone

from src.utils.hash_utils import hash_prompt

_DEFAULT_LOG_PATH = os.path.join("outputs", "llm_calls.jsonl")

def log_call(
    stage: str,
    ticket_id: str,
    provider: str,
    model: str,
    prompt_text: str,
    input_artifacts: list[str],
    output_artifact: str,
    log_path: str = _DEFAULT_LOG_PATH,
) -> None:
    """Append a single LLM-call record to the JSONL log file."""
    record = {
        "stage": stage,
        "ticket_id": ticket_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "model": model,
        "prompt_hash": hash_prompt(prompt_text),
        "input_artifacts": input_artifacts,
        "output_artifact": output_artifact,
    }

    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
