"""
Stage: REPORT_GENERATED

Generates a markdown evaluation report using Jinja2 summarizing the
results of the pipeline, including metrics, route breakdowns, and
auto-generated analytics on failure patterns.
"""

import json
import os
from collections import Counter
from jinja2 import Template

TEMPLATE_STR = """# Evaluation report

## Summary
- Total tickets processed: {{ total_tickets }}
- Auto-send candidates count: {{ auto_send_count }}
- Human review required count: {{ human_review_count }}
- Overall deterministic pass rate: {{ passed_det_count }}/{{ total_tickets }} tickets passed all checks
- Average quality rating: {{ avg_quality_rating | round(1) }}

## Auto-send candidates
{% for t in auto_send_tickets %}
**{{ t.ticket_id }}** ({{ t.issue_type }})
This ticket was routed to auto-send because it achieved a quality rating of {{ t.quality_rating }}/5 with {{ t.policy_risk }} risk, and successfully passed all deterministic checks.
*Excerpt:* "{{ t.excerpt }}"

{% else %}
*No tickets were routed to auto-send.*
{% endfor %}

## Human review required
{% for t in human_review_tickets %}
**{{ t.ticket_id }}** ({{ t.issue_type }})
Primary reason for routing: **{{ t.decision_reason }}**.
Failed checks: {% if t.failed_checks %}{{ t.failed_checks | join(', ') }}{% else %}None{% endif %}.
Quality rating: {{ t.quality_rating }}/5 | Risk level: {{ t.policy_risk }}.
Suggested fix: {{ t.suggested_fix }}

{% else %}
*No tickets required human review.*
{% endfor %}

## Common failure patterns
{{ failure_patterns }}

## Improvement suggestions
{% for sug in suggestions %}
- {{ sug }}
{% endfor %}
"""


def _generate_analytics(final_decisions: list[dict], policy_checks: list[dict], llm_review: list[dict], tickets: list[dict]) -> tuple[str, list[str]]:
    """Compute failure patterns and improvement suggestions dynamically."""
    
    check_map = {c["ticket_id"]: c for c in policy_checks}
    ticket_map = {t["ticket_id"]: t for t in tickets}
    review_map = {r["ticket_id"]: r for r in llm_review}
    
    # Analyze failures
    all_failed_checks = []
    tone_routes = {"auto_send": [], "human_review": []}
    
    for d in final_decisions:
        tid = d["ticket_id"]
        check = check_map.get(tid, {})
        all_failed_checks.extend(check.get("failed_checks", []))
        
        t = ticket_map.get(tid, {})
        tone = t.get("customer_tone", "unknown")
        if d["final_route"] == "human_review":
            tone_routes["human_review"].append(tone)
        else:
            tone_routes["auto_send"].append(tone)
            
    failure_counts = Counter(all_failed_checks)
    hr_tone_counts = Counter(tone_routes["human_review"])
    
    # 1. Format failure patterns
    patterns = []
    if failure_counts:
        most_common_check = failure_counts.most_common(1)[0]
        patterns.append(f"The most frequently failed deterministic check was '{most_common_check[0]}' (failed {most_common_check[1]} times).")
    else:
        patterns.append("All tickets successfully passed the deterministic policy checks.")
        
    if hr_tone_counts:
        most_common_tone = hr_tone_counts.most_common(1)[0]
        patterns.append(f"Tickets with a '{most_common_tone[0]}' tone showed the highest correlation with requiring manual human review ({most_common_tone[1]} occurrences).")
        
    # 2. Format improvement suggestions
    suggestions = []
    
    # Suggestion 1: Address the most common failure
    if failure_counts:
        check = failure_counts.most_common(1)[0][0]
        suggestions.append(f"Adjust the generation prompt to explicitly avoid triggering the `{check}`. Adding few-shot examples of successful compliance may help.")
    else:
        suggestions.append("Deterministic adherence is at 100%. Continue monitoring future batches for regressions in policy checks.")
        
    # Suggestion 2: Tone management
    if hr_tone_counts:
        tone = hr_tone_counts.most_common(1)[0][0]
        suggestions.append(f"Develop a specialized prompt workflow for '{tone}' tone tickets, as they currently represent the majority of human review bottlenecks.")
        
    # Suggestion 3: From LLM Reviews
    # Find a ticket with the most substantial suggested_fix that isn't just "No fixes needed"
    actionable_reviews = [r for r in llm_review if "no significant fixes" not in r.get("suggested_fix", "").lower()]
    if actionable_reviews:
        r = actionable_reviews[0]
        suggestions.append(f"Review the draft logic for {r['ticket_id']}. QA Suggestion: {r.get('suggested_fix')}")
    else:
        suggestions.append("Overall qualitative reviews were excellent. We suggest experimenting with `--variants` to see if a cheaper/faster model can maintain this quality.")
        
    # Ensure we always have 3 suggestions
    while len(suggestions) < 3:
        suggestions.append("Regularly audit the `quality_rubric` definitions to ensure they align with the latest business goals.")
        
    pattern_text = " ".join(patterns)
    return pattern_text, suggestions


def generate_report(
    final_decisions: list[dict],
    policy_checks: list[dict],
    llm_review: list[dict],
    output_path: str = "outputs/evaluation_report.md"
) -> None:
    """Generate the markdown evaluation report."""
    
    # Load original tickets to get issue_type and customer_tone
    # We assume normalized_tickets.json is present in the outputs directory
    # since it's required for the analytics that the PRD specifies.
    tickets_path = os.path.join(os.path.dirname(output_path), "normalized_tickets.json")
    if os.path.exists(tickets_path):
        with open(tickets_path, "r", encoding="utf-8") as f:
            tickets = json.load(f)
    else:
        tickets = []
        
    ticket_map = {t["ticket_id"]: t for t in tickets}
    check_map = {c["ticket_id"]: c for c in policy_checks}
    review_map = {r["ticket_id"]: r for r in llm_review}
    
    total = len(final_decisions)
    auto_sends = [d for d in final_decisions if d["final_route"] == "auto_send"]
    human_reviews = [d for d in final_decisions if d["final_route"] == "human_review"]
    passed_det = sum(1 for d in final_decisions if d["deterministic_passed"])
    avg_quality = sum(d["quality_rating"] for d in final_decisions) / total if total > 0 else 0
    
    auto_send_tickets = []
    for d in auto_sends:
        tid = d["ticket_id"]
        t = ticket_map.get(tid, {})
        
        # Grab the first sentence of the draft reply as an excerpt
        reply = d["draft_reply"]
        first_sentence = reply.split(".")[0].replace("\n", " ").strip() + "..."
        
        auto_send_tickets.append({
            "ticket_id": tid,
            "issue_type": t.get("issue_type", "Unknown"),
            "quality_rating": d["quality_rating"],
            "policy_risk": d["policy_risk"],
            "excerpt": first_sentence
        })
        
    human_review_tickets = []
    for d in human_reviews:
        tid = d["ticket_id"]
        t = ticket_map.get(tid, {})
        check = check_map.get(tid, {})
        review = review_map.get(tid, {})
        
        human_review_tickets.append({
            "ticket_id": tid,
            "issue_type": t.get("issue_type", "Unknown"),
            "decision_reason": d["decision_reason"],
            "failed_checks": check.get("failed_checks", []),
            "quality_rating": d["quality_rating"],
            "policy_risk": d["policy_risk"],
            "suggested_fix": review.get("suggested_fix", "No fix provided.")
        })
        
    patterns, suggestions = _generate_analytics(final_decisions, policy_checks, llm_review, tickets)
    
    template = Template(TEMPLATE_STR)
    markdown = template.render(
        total_tickets=total,
        auto_send_count=len(auto_sends),
        human_review_count=len(human_reviews),
        passed_det_count=passed_det,
        avg_quality_rating=avg_quality,
        auto_send_tickets=auto_send_tickets,
        human_review_tickets=human_review_tickets,
        failure_patterns=patterns,
        suggestions=suggestions
    )
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)
        
    print(f"[REPORTER] Generated evaluation report -> {output_path}")
