"""
Stage: DRAFT_REPLIES_GENERATED

Makes one Gemini API call per ticket to generate a draft support reply,
detects which required reply sections are present in the output, and
writes outputs/draft_replies.json.
"""

import json
import os
import re
import time

import google.generativeai as genai
from dotenv import load_dotenv

from src.utils.llm_logger import log_call

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_NAME = "gemini-2.5-flash"
STAGE_NAME = "draft_generation"

# Section-detection keyword maps (case-insensitive matching)
SECTION_KEYWORDS: dict[str, list[str]] = {
    "greeting": [
        "hello", "hi ", "hi,", "dear", "good morning", "good afternoon",
        "good evening", "welcome", "thank you for reaching out",
        "thank you for contacting", "thanks for contacting",
    ],
    "acknowledgment": [
        "understand", "sorry", "apologize", "apologise", "hear you",
        "i see", "appreciate", "recognise", "recognize", "frustrat",
        "concern", "inconvenience",
    ],
    "resolution_steps": [
        "will", "please", "you can", "we'll", "follow", "step",
        "next", "resolve", "action", "process", "investigate",
        "look into", "assist",
    ],
    "closing": [
        "regards", "sincerely", "best wishes", "thank you",
        "don't hesitate", "do not hesitate", "further assistance",
        "here to help", "reach out", "contact us",
    ],
}


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(ticket: dict, policy: dict) -> str:
    """Build the generation prompt from ticket data and policy rules.

    All content is read from the ticket/policy objects -- nothing is
    hardcoded beyond the structural instruction text.
    """
    # Format account context
    ctx = ticket.get("account_context", {})
    account_lines = "\n".join(
        f"  - {key}: {value}" for key, value in ctx.items()
    )

    # Format required sections
    sections_list = ", ".join(policy["required_reply_sections"])

    # Format forbidden claims
    forbidden_lines = []
    for category, phrases in policy["forbidden_claims"].items():
        label = category.replace("_", " ").title()
        forbidden_lines.append(f"  {label}:")
        for phrase in phrases:
            forbidden_lines.append(f"    - \"{phrase}\"")
    forbidden_text = "\n".join(forbidden_lines)

    prompt = (
        f"You are a customer support agent. Draft a helpful support reply "
        f"for the following ticket.\n\n"
        f"TICKET DETAILS:\n"
        f"  Ticket ID: {ticket['ticket_id']}\n"
        f"  Customer Tone: {ticket['customer_tone']}\n"
        f"  Issue Type: {ticket['issue_type']}\n"
        f"  Customer Message: {ticket['customer_message']}\n\n"
        f"ACCOUNT CONTEXT:\n{account_lines}\n\n"
        f"POLICY RULES:\n"
        f"  Required reply sections: {sections_list}\n\n"
        f"  Forbidden claims (do NOT include any of these):\n{forbidden_text}\n\n"
        f"INSTRUCTION:\n"
        f"Draft a helpful support reply. Do not make any forbidden claims. "
        f"Do not request sensitive credentials. Structure your reply so it "
        f"clearly contains the required sections."
    )
    return prompt


# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------

def _detect_sections(
    reply_text: str,
    required_sections: list[str],
) -> list[str]:
    """Return the list of required section names detected in *reply_text*.

    Detection uses case-insensitive keyword matching against the
    SECTION_KEYWORDS map.  For section names not in the map we fall back
    to checking whether the section name itself (or a normalised variant)
    appears in the reply.
    """
    lower_reply = reply_text.lower()
    found: list[str] = []

    for section in required_sections:
        keywords = SECTION_KEYWORDS.get(section, [section.replace("_", " ")])
        if any(kw.lower() in lower_reply for kw in keywords):
            found.append(section)

    return found


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_drafts(
    tickets: list[dict],
    policy: dict,
    outputs_dir: str = "outputs",
) -> list[dict]:
    """Generate one draft reply per ticket via Gemini.

    Parameters
    ----------
    tickets : list[dict]
        Normalised tickets from the loader stage.
    policy : dict
        Policy configuration.
    outputs_dir : str
        Directory for output artefacts.

    Returns
    -------
    list[dict]
        List of ``{ticket_id, reply_text, reply_sections_present}`` dicts.
    """

    # --- Initialise Gemini ------------------------------------------------ #
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not found. Set it in .env or as an env var."
        )
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)

    required_sections = policy["required_reply_sections"]
    drafts: list[dict] = []

    for i, ticket in enumerate(tickets):
        tid = ticket["ticket_id"]
        prompt = _build_prompt(ticket, policy)

        print(f"[GENERATOR] ({i + 1}/{len(tickets)}) Generating draft for {tid}...")

        # --- Call Gemini (one call per ticket) ---------------------------- #
        t0 = time.perf_counter()
        response = model.generate_content(prompt)
        latency_ms = (time.perf_counter() - t0) * 1000

        reply_text = response.text.strip()

        # --- Detect sections --------------------------------------------- #
        sections_present = _detect_sections(reply_text, required_sections)

        drafts.append({
            "ticket_id": tid,
            "reply_text": reply_text,
            "reply_sections_present": sections_present,
        })

        # --- Log the call ------------------------------------------------ #
        log_call(
            stage="draft_generation",
            ticket_id=tid,
            provider="google",
            model=MODEL_NAME,
            prompt_text=prompt,
            input_artifacts=["outputs/normalized_tickets.json", "policy.json"],
            output_artifact="outputs/draft_replies.json"
        )

        print(f"[GENERATOR] {tid}: sections detected = {sections_present} "
              f"({latency_ms:.0f}ms)")

    # --- Write artifact --------------------------------------------------- #
    os.makedirs(outputs_dir, exist_ok=True)
    out_path = os.path.join(outputs_dir, "draft_replies.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(drafts, f, indent=2, ensure_ascii=False)

    print(f"[GENERATOR] Wrote {len(drafts)} draft replies -> {out_path}")
    return drafts
