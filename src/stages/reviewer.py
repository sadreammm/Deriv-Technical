"""
Stage: LLM_REVIEW_COMPLETE

Uses Gemini to review the generated draft replies against the policy and ticket,
outputting a structured JSON review (quality rating, policy risk, summary, fix).
"""

import json
import os
import time

import google.generativeai as genai
from dotenv import load_dotenv

from src.utils.llm_logger import log_call

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_NAME = "gemini-2.5-flash"
STAGE_NAME = "llm_review"


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_review_prompt(ticket: dict, draft: dict, check: dict, policy: dict) -> str:
    """Build the prompt for the reviewer LLM, including all constraints."""
    
    # 1. Format required sections
    sections_list = ", ".join(policy.get("required_reply_sections", []))
    
    # 2. Format forbidden claims
    forbidden_lines = []
    for category, phrases in policy.get("forbidden_claims", {}).items():
        label = category.replace("_", " ").title()
        forbidden_lines.append(f"  {label}:")
        for phrase in phrases:
            forbidden_lines.append(f"    - \"{phrase}\"")
    forbidden_text = "\n".join(forbidden_lines)

    # 3. Format quality rubric
    rubric_lines = []
    for score, desc in policy.get("quality_rubric", {}).items():
        rubric_lines.append(f"  {score}: {desc}")
    rubric_text = "\n".join(rubric_lines)
    
    prompt = (
        f"You are a Quality Assurance reviewer for customer support.\n\n"
        f"--- TICKET ---\n"
        f"{json.dumps(ticket, indent=2)}\n\n"
        f"--- DRAFT REPLY TO REVIEW ---\n"
        f"{draft.get('reply_text', '')}\n\n"
        f"--- POLICY CONSTRAINTS ---\n"
        f"Required Sections: {sections_list}\n"
        f"Forbidden Claims:\n{forbidden_text}\n\n"
        f"--- DETERMINISTIC CHECKS RESULT ---\n"
        f"Score: {check.get('deterministic_score')}/5. Passed All: {check.get('passed')}. Failed: {check.get('failed_checks', [])}\n\n"
        f"--- QUALITY RUBRIC ---\n"
        f"{rubric_text}\n\n"
        f"INSTRUCTION:\n"
        f"Review the draft reply based on the ticket context and policy rules.\n"
        f"Respond with ONLY valid JSON matching this schema:\n"
        f"{{\n"
        f"  \"quality_rating\": <integer 1-5>,\n"
        f"  \"policy_risk\": <\"low\" | \"medium\" | \"high\">,\n"
        f"  \"review_summary\": <string, max 120 words>,\n"
        f"  \"suggested_fix\": <string, max 80 words>\n"
        f"}}\n"
        f"Respond with only valid JSON. No markdown, no preamble, no explanation outside the JSON object."
    )
    return prompt

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_and_validate_json(response_text: str) -> dict:
    """Parse JSON and enforce schema/risk limits."""
    text = response_text.strip()
    
    # Clean possible markdown formatting
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    data = json.loads(text)
    
    # Coerce policy_risk if invalid
    risk = str(data.get("policy_risk", "high")).lower()
    if risk not in ("low", "medium", "high"):
        risk = "high"
        
    return {
        "quality_rating": int(data.get("quality_rating", 1)),
        "policy_risk": risk,
        "review_summary": str(data.get("review_summary", "")),
        "suggested_fix": str(data.get("suggested_fix", ""))
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def review_drafts(
    tickets: list[dict],
    draft_replies: list[dict],
    policy_checks: list[dict],
    policy: dict,
    outputs_dir: str = "outputs"
) -> list[dict]:
    """Execute LLM reviews for all tickets."""
    
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not found. Set it in .env or as an env var.")
    
    genai.configure(api_key=api_key)
    
    # We use response_mime_type to force Gemini into JSON mode
    model = genai.GenerativeModel(
        MODEL_NAME,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json"
        )
    )
    
    draft_map = {d["ticket_id"]: d for d in draft_replies}
    check_map = {c["ticket_id"]: c for c in policy_checks}
    
    results = []
    
    for i, ticket in enumerate(tickets):
        tid = ticket["ticket_id"]
        draft = draft_map.get(tid, {})
        check = check_map.get(tid, {})
        
        prompt = _build_review_prompt(ticket, draft, check, policy)
        print(f"[REVIEWER] ({i+1}/{len(tickets)}) Reviewing draft for {tid}...")
        
        parsed_data = None
        for attempt in range(2):
            try:
                t0 = time.perf_counter()
                response = model.generate_content(prompt)
                latency_ms = (time.perf_counter() - t0) * 1000
                reply_text = response.text
                
                log_call(
                    stage="llm_review",
                    ticket_id=tid,
                    provider="google",
                    model=MODEL_NAME,
                    prompt_text=prompt,
                    input_artifacts=["outputs/normalized_tickets.json", "outputs/draft_replies.json", "outputs/policy_checks.json", "policy.json"],
                    output_artifact="outputs/llm_review.json"
                )
                
                parsed_data = _parse_and_validate_json(reply_text)
                break  # Exit retry loop on success
                
            except Exception as e:
                print(f"[REVIEWER] {tid}: JSON parse/API failed on attempt {attempt+1}: {e}")
                # Will loop and retry if attempt == 0
                
        # If parsing completely failed after retries, fallback
        if parsed_data is None:
            parsed_data = {
                "quality_rating": 1,
                "policy_risk": "high",
                "review_summary": "Review parsing failed.",
                "suggested_fix": "Manual review required."
            }
            
        results.append({
            "ticket_id": tid,
            "quality_rating": parsed_data["quality_rating"],
            "policy_risk": parsed_data["policy_risk"],
            "review_summary": parsed_data["review_summary"],
            "suggested_fix": parsed_data["suggested_fix"]
        })
        
        print(f"[REVIEWER] {tid}: rating={parsed_data['quality_rating']}/5, risk={parsed_data['policy_risk']}")
        
    os.makedirs(outputs_dir, exist_ok=True)
    out_path = os.path.join(outputs_dir, "llm_review.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print(f"[REVIEWER] Wrote {len(results)} reviews -> {out_path}")
    return results
