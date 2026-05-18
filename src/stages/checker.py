"""
Stage: DETERMINISTIC_CHECKS_COMPLETE

Runs deterministic python checks on draft replies and scores them (0-5).
"""
import json
import os
import re

# ---------------------------------------------------------------------------
# Individual Checks
# ---------------------------------------------------------------------------

def _check_sections_present(draft: dict, policy: dict) -> bool:
    """True if all policy required_reply_sections appear in draft."""
    required = set(policy.get("required_reply_sections", []))
    present = set(draft.get("reply_sections_present", []))
    return required.issubset(present)

def _check_password_request(reply_text: str) -> bool:
    """True if reply does NOT contain password request phrases."""
    text = reply_text.lower()
    forbidden = ["password", "full password", "enter your password", "provide your password"]
    for phrase in forbidden:
        if phrase in text:
            return False
    return True

def _check_guaranteed_timeline(reply_text: str) -> bool:
    """True if reply does NOT contain guaranteed timeline patterns."""
    text = reply_text.lower()
    patterns = [
        r"will be resolved in \w+",
        r"guaranteed within",
        r"you will receive by",
        r"approved in \w+ (hours|days)",
        r"released within",
        r"definitely by",
        r"100% within"
    ]
    for p in patterns:
        if re.search(p, text):
            return False
    return True

def _check_funds_released(reply_text: str, ticket: dict) -> bool:
    """True if reply does NOT claim funds released when not actually released."""
    ctx = ticket.get("account_context", {})
    if ctx.get("withdrawal_status") == "released":
        return True
    
    text = reply_text.lower()
    forbidden = [
        "funds have been released",
        "money is on its way",
        "transfer is complete",
        "funds are available",
        "money has been sent",
        "withdrawal has been processed"
    ]
    for phrase in forbidden:
        if phrase in text:
            return False
    return True

def _check_blame_language(reply_text: str) -> bool:
    """True if reply does NOT contain blaming/dismissive language."""
    text = reply_text.lower()
    forbidden = [
        "you should have",
        "that was your fault",
        "you failed to",
        "as we stated",
        "clearly stated in our terms",
        "this is your fault",
        "that's not our problem",
        "we don't care"
    ]
    for phrase in forbidden:
        if phrase in text:
            return False
    return True

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_checks(
    tickets: list[dict],
    drafts: list[dict],
    policy: dict,
    outputs_dir: str = "outputs"
) -> list[dict]:
    """Run all checks and score each draft. Write outputs/policy_checks.json."""
    
    draft_map = {d["ticket_id"]: d for d in drafts}
    results = []
    
    for ticket in tickets:
        tid = ticket["ticket_id"]
        draft = draft_map.get(tid)
        if not draft:
            raise ValueError(f"No draft found for ticket {tid}")
            
        reply_text = draft.get("reply_text", "")
        
        # 1. Run the 5 checks
        checks = {
            "sections_present_check": _check_sections_present(draft, policy),
            "password_request_check": _check_password_request(reply_text),
            "guaranteed_timeline_check": _check_guaranteed_timeline(reply_text),
            "funds_released_check": _check_funds_released(reply_text, ticket),
            "blame_language_check": _check_blame_language(reply_text)
        }
        
        failed_checks = [name for name, passed in checks.items() if not passed]
        passed_all = len(failed_checks) == 0
        
        # 2. Deterministic score (0-5)
        deterministic_score = 5 - len(failed_checks)
        
        # 3. must_human_review boolean
        must_human_review = False
        if not passed_all:
            must_human_review = True
        elif ticket.get("customer_tone") == "angry":
            must_human_review = True
        elif ticket.get("issue_type") == "bonus_dispute":
            must_human_review = True
            
        results.append({
            "ticket_id": tid,
            "passed": passed_all,
            "failed_checks": failed_checks,
            "must_human_review": must_human_review,
            "deterministic_score": deterministic_score
        })
        
        print(f"[CHECKER] {tid}: score={deterministic_score}/5, human_review={must_human_review}")
        if not passed_all:
            print(f"          Failed checks: {failed_checks}")
        
    os.makedirs(outputs_dir, exist_ok=True)
    out_path = os.path.join(outputs_dir, "policy_checks.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print(f"[CHECKER] Wrote {len(results)} policy checks -> {out_path}")
    return results
