"""
Stage: HUMAN_OVERRIDE_COMPLETE

Computes the initial routing for tickets based on checks and reviews,
and prompts the user for manual overrides unless --ci mode is active.
"""

import json
import os
import sys

def run_override_checkpoint(
    tickets: list[dict],
    policy_checks: list[dict],
    llm_review: list[dict],
    ci_mode: bool = False,
    outputs_dir: str = "outputs"
) -> dict[str, str]:
    """Compute routes, handle optional human overrides, and write overrides JSON."""
    
    checks_map = {c["ticket_id"]: c for c in policy_checks}
    review_map = {r["ticket_id"]: r for r in llm_review}
    
    initial_routes = {}
    final_routes = {}
    
    print("\n--- TICKET ROUTING SUMMARY ---")
    
    for ticket in tickets:
        tid = ticket["ticket_id"]
        check = checks_map.get(tid, {})
        review = review_map.get(tid, {})
        
        det_pass = check.get("passed", False)
        det_label = "PASS" if det_pass else "FAIL"
        
        quality = review.get("quality_rating", 1)
        risk = review.get("policy_risk", "high")
        
        # Compute initial route per prompt rules
        route = "auto_send"
        if check.get("must_human_review", False):
            route = "human_review"
        elif risk == "high":
            route = "human_review"
        elif quality <= 2:
            route = "human_review"
            
        initial_routes[tid] = route
        final_routes[tid] = route
        
        print(f"[{tid}] det:{det_label:<4} quality:{quality}  risk:{risk:<6} -> {route}")

    # Handle optional overrides
    overrides_list = []
    operator_skipped = False
    
    if ci_mode:
        print("\n[OVERRIDE] --ci flag active: skipping interactive override prompt.")
        operator_skipped = True
    else:
        print("\nEnter any ticket overrides as: <ticket_id> <auto_send|human_review>")
        print("Press Enter on an empty line to continue.")
        
        while True:
            try:
                # Provide a prompt without buffering issues
                sys.stdout.write("> ")
                sys.stdout.flush()
                
                line = sys.stdin.readline()
                if not line: # EOF
                    break
                line = line.strip()
                if not line: # Empty line
                    break
                    
                parts = line.split()
                if len(parts) != 2:
                    print("  [Warning] Invalid format. Expected: <ticket_id> <route>")
                    continue
                    
                tid, route = parts[0], parts[1]
                
                if tid not in initial_routes:
                    print(f"  [Warning] Unknown ticket_id: {tid}")
                    continue
                    
                if route not in ("auto_send", "human_review"):
                    print(f"  [Warning] Invalid route '{route}'. Allowed: auto_send, human_review")
                    continue
                    
                overrides_list.append({
                    "ticket_id": tid,
                    "override_route": route
                })
                final_routes[tid] = route
                print(f"  [Override applied] {tid} -> {route}")
                
            except EOFError:
                break

    # Write output JSON
    os.makedirs(outputs_dir, exist_ok=True)
    out_path = os.path.join(outputs_dir, "human_overrides.json")
    
    output_data = {
        "overrides": overrides_list,
        "operator_skipped": operator_skipped
    }
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
        
    print(f"\n[OVERRIDE] Wrote overrides -> {out_path}")
    return final_routes
