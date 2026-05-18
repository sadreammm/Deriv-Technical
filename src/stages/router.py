"""
Stage: FINAL_ROUTING_DECIDED

Consolidates all evaluations and overrides to compute the final routing
decisions for each ticket, outputting them to outputs/final_decisions.json.
"""

import json
import os

def compute_final_decisions(
    tickets: list[dict],
    draft_replies: list[dict],
    policy_checks: list[dict],
    llm_review: list[dict],
    route_map: dict[str, str],
    outputs_dir: str = "outputs"
) -> list[dict]:
    """Compute and write final routing decisions for all tickets."""
    
    draft_map = {d["ticket_id"]: d for d in draft_replies}
    check_map = {c["ticket_id"]: c for c in policy_checks}
    review_map = {r["ticket_id"]: r for r in llm_review}
    
    decisions = []
    
    for ticket in tickets:
        tid = ticket["ticket_id"]
        draft = draft_map.get(tid, {})
        check = check_map.get(tid, {})
        review = review_map.get(tid, {})
        
        # Determine initial route
        quality = review.get("quality_rating", 1)
        risk = review.get("policy_risk", "high")
        det_passed = check.get("passed", False)
        
        initial_route = "auto_send"
        if check.get("must_human_review", False):
            initial_route = "human_review"
        elif risk == "high":
            initial_route = "human_review"
        elif quality <= 2:
            initial_route = "human_review"
            
        final_route = route_map.get(tid, initial_route)
        
        # Determine decision reason (priority order)
        reason = "passed_all_checks"
        if final_route != initial_route:
            reason = "operator_override"
        elif not det_passed:
            reason = "det_fail"
        elif ticket.get("customer_tone") == "angry":
            reason = "angry_tone"
        elif ticket.get("issue_type") == "bonus_dispute":
            reason = "bonus_dispute"
        elif quality <= 2:
            reason = "low_quality"
        elif risk == "high":
            reason = "high_risk"
            
        decisions.append({
            "ticket_id": tid,
            "draft_reply": draft.get("reply_text", ""),
            "deterministic_passed": det_passed,
            "quality_rating": quality,
            "policy_risk": risk,
            "initial_route": initial_route,
            "final_route": final_route,
            "decision_reason": reason
        })
        
    os.makedirs(outputs_dir, exist_ok=True)
    out_path = os.path.join(outputs_dir, "final_decisions.json")
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(decisions, f, indent=2, ensure_ascii=False)
        
    print(f"[ROUTER] Wrote {len(decisions)} final decisions -> {out_path}")
    return decisions
