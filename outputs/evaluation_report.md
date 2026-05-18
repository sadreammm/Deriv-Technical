# Evaluation report

## Summary
- Total tickets processed: 5
- Auto-send candidates count: 2
- Human review required count: 3
- Overall deterministic pass rate: 5/5 tickets passed all checks
- Average quality rating: 5.0

## Auto-send candidates

**TKT-003** (account_verification)
This ticket was routed to auto-send because it achieved a quality rating of 5/5 with low risk, and successfully passed all deterministic checks.
*Excerpt:* "Subject: Re: Your Account Verification Status - TKT-003  Hi there,  Thank you for reaching out to us regarding your account verification status..."


**TKT-004** (platform_error)
This ticket was routed to auto-send because it achieved a quality rating of 5/5 with low risk, and successfully passed all deterministic checks.
*Excerpt:* "Dear Valued Trader,  Thank you for reaching out regarding the issues you're experiencing when trying to place trades, Ticket ID TKT-004..."



## Human review required

**TKT-001** (withdrawal_delay)
Primary reason for routing: **operator_override**.
Failed checks: None.
Quality rating: 5/5 | Risk level: low.
Suggested fix: No significant fixes are needed as the draft is comprehensive, empathetic, and fully compliant. It serves as an exemplary response for a frustrated customer.


**TKT-002** (bonus_dispute)
Primary reason for routing: **angry_tone**.
Failed checks: None.
Quality rating: 5/5 | Risk level: low.
Suggested fix: No significant fixes are required. The draft is exceptionally well-crafted, empathetic, and fully compliant with all policies. It proactively addresses the customer's concerns and outlines clear next steps effectively.


**TKT-005** (withdrawal_delay)
Primary reason for routing: **angry_tone**.
Failed checks: None.
Quality rating: 5/5 | Risk level: low.
Suggested fix: No significant fixes needed. The response is highly effective and addresses all aspects of the customer's complaint and concerns proactively and empathetically.



## Common failure patterns
All tickets successfully passed the deterministic policy checks. Tickets with a 'angry' tone showed the highest correlation with requiring manual human review (2 occurrences).

## Improvement suggestions

- Deterministic adherence is at 100%. Continue monitoring future batches for regressions in policy checks.

- Develop a specialized prompt workflow for 'angry' tone tickets, as they currently represent the majority of human review bottlenecks.

- Overall qualitative reviews were excellent. We suggest experimenting with `--variants` to see if a cheaper/faster model can maintain this quality.
