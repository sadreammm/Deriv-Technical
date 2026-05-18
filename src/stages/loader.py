"""
Stage: INPUTS_LOADED

Reads tickets.json and policy.json, validates required fields,
normalises ticket data, and writes outputs/normalized_tickets.json.
"""

import json
import os
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------

REQUIRED_TICKET_FIELDS = [
    "ticket_id",
    "customer_tone",
    "issue_type",
    "customer_message",
    "account_context",
]

REQUIRED_POLICY_KEYS = [
    "required_reply_sections",
    "forbidden_claims",
    "routing_rules",
    "quality_rubric",
]

ACCOUNT_CONTEXT_SUBFIELDS = [
    "account_type",
    "account_age_days",
    "balance",
    "recent_transactions",
    "kyc_status",
]


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_ticket(ticket: dict, index: int, allowed_issue_types: list[str]) -> None:
    """Raise ValueError if a ticket is missing required fields or has a
    disallowed issue_type."""
    for field in REQUIRED_TICKET_FIELDS:
        if field not in ticket:
            raise ValueError(
                f"Ticket at index {index} (id={ticket.get('ticket_id', 'UNKNOWN')}) "
                f"is missing required field: '{field}'"
            )

    issue = ticket["issue_type"]
    if issue not in allowed_issue_types:
        raise ValueError(
            f"Ticket '{ticket['ticket_id']}' has invalid issue_type '{issue}'. "
            f"Allowed types: {allowed_issue_types}"
        )


def _validate_policy(policy: dict) -> None:
    """Raise ValueError if the policy is missing any required top-level key."""
    for key in REQUIRED_POLICY_KEYS:
        if key not in policy:
            raise ValueError(f"Policy is missing required key: '{key}'")


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def _strip_strings(obj):
    """Recursively strip whitespace from all string values."""
    if isinstance(obj, str):
        return obj.strip()
    if isinstance(obj, dict):
        return {k: _strip_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_strip_strings(item) for item in obj]
    return obj


def _normalise_ticket(ticket: dict) -> dict:
    """Return a normalised copy of a single ticket."""
    ticket = _strip_strings(ticket)

    # Ensure all expected account_context sub-fields exist
    ctx = ticket.get("account_context") or {}
    if not isinstance(ctx, dict):
        ctx = {}
    for subfield in ACCOUNT_CONTEXT_SUBFIELDS:
        ctx.setdefault(subfield, None)
    ticket["account_context"] = ctx

    # Stamp load time
    ticket["loaded_at"] = datetime.now(timezone.utc).isoformat()

    return ticket


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_inputs(
    tickets_path: str = "tickets.json",
    policy_path: str = "policy.json",
    outputs_dir: str = "outputs",
) -> tuple[list[dict], dict]:
    """Load, validate, and normalise pipeline inputs.

    Parameters
    ----------
    tickets_path : str
        Path to the tickets JSON file (list of ticket objects).
    policy_path : str
        Path to the policy JSON file.
    outputs_dir : str
        Directory where normalised artefacts are written.

    Returns
    -------
    tuple[list[dict], dict]
        (normalised_tickets, policy)

    Raises
    ------
    FileNotFoundError
        If either input file is missing.
    ValueError
        If validation of tickets or policy fails.
    """

    # --- Load raw files --------------------------------------------------- #
    if not os.path.isfile(tickets_path):
        raise FileNotFoundError(f"Tickets file not found: {tickets_path}")
    if not os.path.isfile(policy_path):
        raise FileNotFoundError(f"Policy file not found: {policy_path}")

    with open(tickets_path, "r", encoding="utf-8") as f:
        tickets: list[dict] = json.load(f)
    with open(policy_path, "r", encoding="utf-8") as f:
        policy: dict = json.load(f)

    # --- Validate policy first (need allowed_issue_types for tickets) ----- #
    _validate_policy(policy)
    allowed_issue_types = policy.get("allowed_issue_types", [])

    # --- Validate tickets ------------------------------------------------- #
    if not isinstance(tickets, list):
        raise ValueError("tickets.json must contain a JSON array of ticket objects.")
    for idx, ticket in enumerate(tickets):
        _validate_ticket(ticket, idx, allowed_issue_types)

    # --- Normalise -------------------------------------------------------- #
    normalised = [_normalise_ticket(t) for t in tickets]

    # --- Write artifact --------------------------------------------------- #
    os.makedirs(outputs_dir, exist_ok=True)
    out_path = os.path.join(outputs_dir, "normalized_tickets.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(normalised, f, indent=2, ensure_ascii=False)

    print(f"[LOADER] Wrote {len(normalised)} normalised tickets -> {out_path}")
    return normalised, policy
