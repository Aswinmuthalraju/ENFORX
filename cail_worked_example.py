"""
CAIL Worked Example: Realistic Trade Case
This script demonstrates the Causal Audit Intelligence Layer (CAIL) in action
by simulating a trade that requires correction and showing the intelligence output.
"""

from __future__ import annotations
from main import run_pipeline
import json
import os
from pathlib import Path

def run_demo():
    print("\n" + "="*80)
    print("  ENFORX CAIL DEMO: High-Assurance Causal Audit Intelligence")
    print("="*80 + "\n")

    # CASE: User wants to buy 50 shares of AAPL.
    # POLICY: max_per_order = 10.
    # EXPECTATION: 
    # 1. FDEE corrects 50 -> 10.
    # 2. CAIL detects this deviation.
    # 3. CAIL simulates the counterfactual (Breach if not corrected).
    # 4. CAIL suggests tightening Layer 3 reasoning fence.
    
    print("[STEP 1] Running pipeline for 'Buy 50 shares of AAPL'...")
    user_input = "Buy 50 shares of AAPL"
    result = run_pipeline(user_input)
    
    audit_entry = result["audit_entry"]
    
    print("\n" + "-"*80)
    print("  CAIL INTELLIGENCE REPORT")
    print("-"*80)
    
    print(f"  EVENT: {audit_entry['event']}")
    print(f"  RISK SCORE: {audit_entry['risk_score']}")
    print(f"  CONFIDENCE: {audit_entry['confidence']}")
    
    print("\n  [1] CAUSAL RECONSTRUCTION")
    print(f"      - Intent Formalized: {audit_entry['causal_chain']['intent_formalization']}")
    print(f"      - Deviation Point:   {audit_entry['deviation_point']}")
    print(f"      - Lineage Flow:      {' -> '.join(audit_entry['causal_chain']['lineage'])}")
    
    print("\n  [2] COUNTERFACTUAL SIMULATION")
    print(f"      - Scenario: {audit_entry['counterfactual']['scenario']}")
    print(f"      - Outcome:  {audit_entry['counterfactual']['outcome']}")
    print(f"      - Risk Δ:   {audit_entry['counterfactual']['risk_delta']}")
    print(f"      - Insight:  {audit_entry['counterfactual']['explanation']}")
    
    print("\n  [3] BEHAVIORAL PROFILING")
    print(f"      - Risk Appetite: {audit_entry['behavior_profile']['risk_appetite']}")
    print(f"      - Anomaly Type:  {audit_entry['anomaly_type']}")
    
    print("\n  [4] POLICY PRESSURE POINTS")
    for pp in audit_entry["policy_pressure_points"]:
        print(f"      - Rule: {pp['rule']} | Pressure: {pp['pressure']}")
        print(f"        Suggestion: {pp['suggestion']}")
        
    print("\n  [5] SYSTEM RECOMMENDATIONS")
    for rec in audit_entry["recommendations"]:
        print(f"      - TARGET: {rec['target_layer']}")
        print(f"        ACTION: {rec['action']}")
        print(f"        REASON: {rec['reason']}")
    
    print("\n" + "="*80)
    print("  DEMO COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    run_demo()
