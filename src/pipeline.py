"""
Main pipeline entry point for Customer Support AI Evaluation.
"""

import argparse
import enum
import os
import sys
import subprocess
from dotenv import load_dotenv

from src.stages.loader import load_inputs
from src.stages.generator import generate_drafts
from src.stages.checker import run_checks
from src.stages.reviewer import review_drafts
from src.stages.override import run_override_checkpoint
from src.stages.router import compute_final_decisions
from src.stages.reporter import generate_report

class PipelineState(enum.Enum):
    INIT = 1
    INPUTS_LOADED = 2
    DRAFT_REPLIES_GENERATED = 3
    DETERMINISTIC_CHECKS_COMPLETE = 4
    LLM_REVIEW_COMPLETE = 5
    HUMAN_OVERRIDE_COMPLETE = 6
    FINAL_ROUTING_DECIDED = 7
    REPORT_GENERATED = 8
    VALIDATION_COMPLETE = 9
    RESULTS_FINALISED = 10

def transition(current: PipelineState, expected_next: PipelineState) -> PipelineState:
    if current.value + 1 != expected_next.value:
        raise ValueError(f"Invalid transition from {current.name} to {expected_next.name}. "
                         f"Expected {PipelineState(current.value + 1).name}.")
    
    print(f"[PIPELINE] {current.name} -> {expected_next.name}")
    return expected_next

def run_pipeline(args):
    # Load API key
    load_dotenv()
    if not os.environ.get("GEMINI_API_KEY"):
        print("[ERROR] GEMINI_API_KEY not set in environment or .env")
        sys.exit(1)
        
    state = PipelineState.INIT
    print("\n=== Starting Evaluation Pipeline ===")
    
    try:
        # Stage 1: Loader
        state = transition(state, PipelineState.INPUTS_LOADED)
        tickets, policy = load_inputs(args.tickets, args.policy)
        
        # Stage 2: Generator
        state = transition(state, PipelineState.DRAFT_REPLIES_GENERATED)
        drafts = generate_drafts(tickets, policy)
        
        # Stage 3: Checker
        state = transition(state, PipelineState.DETERMINISTIC_CHECKS_COMPLETE)
        checks = run_checks(tickets, drafts, policy)
        
        # Stage 4: Reviewer
        state = transition(state, PipelineState.LLM_REVIEW_COMPLETE)
        reviews = review_drafts(tickets, drafts, checks, policy)
        
        # Stage 5: Override
        state = transition(state, PipelineState.HUMAN_OVERRIDE_COMPLETE)
        routes = run_override_checkpoint(tickets, checks, reviews, ci_mode=args.ci)
        
        # Stage 6: Router
        state = transition(state, PipelineState.FINAL_ROUTING_DECIDED)
        decisions = compute_final_decisions(tickets, drafts, checks, reviews, routes)
        
        # Stage 7: Reporter
        state = transition(state, PipelineState.REPORT_GENERATED)
        generate_report(decisions, checks, reviews)
        
        # Stage 8: Validator
        state = transition(state, PipelineState.VALIDATION_COMPLETE)
        print("[PIPELINE] Running validation script...")
        val_result = subprocess.run([sys.executable, "validate.py"], capture_output=True, text=True)
        if val_result.returncode != 0:
            print("[WARNING] validate.py failed or returned non-zero.")
            print(val_result.stderr)
        else:
            print("[PIPELINE] Validation script passed.")
            
        # Stage 9: Finalise
        state = transition(state, PipelineState.RESULTS_FINALISED)
        
        print("\n=== FINAL RESULTS SUMMARY ===")
        print(f"{'Ticket':<10} | {'Route':<15} | {'Quality':<7} | {'Risk':<5}")
        print("-" * 45)
        for dec in decisions:
            print(f"{dec['ticket_id']:<10} | {dec['final_route']:<15} | {dec['quality_rating']:<7} | {dec['policy_risk']:<5}")
            
        print("-" * 45)
        print(f"Total LLM calls executed: {len(tickets) * 2} ({len(tickets)} generation + {len(tickets)} review)")
        
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed at stage: {state.name}")
        print(f"Details: {str(e)}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Customer Support AI Evaluation Pipeline")
    parser.add_argument("--ci", action="store_true", help="Non-interactive mode. Skips human overrides.")
    parser.add_argument("--tickets", type=str, default="tickets.json", help="Path to tickets JSON file.")
    parser.add_argument("--policy", type=str, default="policy.json", help="Path to policy JSON file.")
    parser.add_argument("--variants", action="store_true", help="Enable prompt variant comparison (optional).")
    args = parser.parse_args()
    
    run_pipeline(args)

if __name__ == "__main__":
    main()
