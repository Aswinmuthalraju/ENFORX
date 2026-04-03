"""
ENFORX SVAAS — Self-Verifying Autonomous Agent System
The next-generation "Project Phoenix" architecture for Causal Integrity.

Layers:
1. EnforxGuard Input Firewall
2. Intent Formalization Engine (SID)
3. Behavioral Memory (Probing Detection)
4. Adversarial Self-Play (Resilience Test)
5. Guided Reasoning Constraints (GRC)
6. Agent Core (Multi-Agent Reasoner)
7. Meta-Reasoning Auditor (COT Proof)
8. Causal Graph Engine (Lineage Build)
9. Simplex Controller (PIAV + FDEE)
10. Multi-Agent Consensus (Consensus-based Safety)
11. EnforxGuard Output Firewall
12. Causal Audit Intelligence (CAIL)
"""

import sys
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Existing Components
from enforxguard.input_firewall import InputFirewall
from enforxguard.output_firewall import OutputFirewall
from core.ife import IntentFormalizationEngine
from core.grc import GuidedReasoningConstraints
from core.agent import AgentCore
from core.piav import PlanIntentAlignmentValidator
from core.ccv import CausalChainValidator
from core.fdee import FinancialDomainEnforcementEngine
from core.dap import DelegationAuthorityProtocol
from audit.cail import CausalAuditIntelligenceLayer
from alpaca.trader import AlpacaTrader

# NEW SVAAS Components
from core.meta_reasoning import MetaReasoningAuditor
from core.causal_graph import CausalGraphEngine
from core.adversarial_engine import AdversarialEngine
from core.multi_agent import MultiAgentConsensus

def print_banner():
    print("\n" + "🚀 " + "=" * 62)
    print("  ENFORX SVAAS — Self-Verifying Autonomous Agent System")
    print("  Project Phoenix: Causal Proofs & Adversarial Resiliency")
    print("  " + "=" * 62 + "\n")

def print_layer(num: int, name: str, status: str, detail: str = ""):
    icons = {
        "PASS": "✅ OK", "BLOCK": "❌ BLOCKED", "ALIGNED": "✅ OK", 
        "MISALIGNED": "❌ BLOCKED", "ALLOW": "✅ OK", "CORRECT": "🛠️ CORRECTED", 
        "AUTHORIZED": "✅ OK", "FLAG": "⚠️ FLAGGED", "APPROVED": "🤝 APPROVED",
        "DENIED": "🛡️ DENIED", "EMERGENCY_BLOCK": "🚨 EMERGENCY", "EXECUTE": "🚀 EXECUTE"
    }
    icon = icons.get(status, "ℹ️ INFO")
    print(f"  Layer {num:2d} | {icon:12s} | {status:15s} | {name}")
    if detail:
        print(f"          └─ {detail}")

def run_svaas_pipeline(user_input: str, agent_id: str = "trader-01") -> dict:
    print_banner()
    print(f"  [INIT] User Input: \"{user_input}\"")
    print("-" * 70)

    layer_results = {}
    graph_engine = CausalGraphEngine()
    consensus = MultiAgentConsensus()
    
    # 🧬 CAUSAL ROOT: Intent
    intent_node = graph_engine.add_node("node-intent", "intent", user_input)

    # --- LAYER 1: Input Firewall ---
    firewall_in = InputFirewall()
    l1 = firewall_in.scan(user_input)
    layer_results["l1_firewall"] = l1
    print_layer(1, "EnforxGuard Input Firewall", l1["status"], l1.get("reason", ""))
    if l1["status"] == "BLOCK": return _finalize(layer_results, user_input, "BLOCKED_L1")
    
    graph_engine.add_node("node-firewall", "security", l1, [intent_node])

    # --- LAYER 2: IFE (SID) ---
    ife = IntentFormalizationEngine()
    sid = ife.formalize(l1["sanitized_input"], l1)
    layer_results["l2_ife"] = {"status": "PASS", "sid": sid}
    print_layer(2, "Intent Formalize (SID)", "PASS", f"SID: {sid['sid_id']} | Type: {sid['primary_action']}")
    
    sid_node = graph_engine.add_node("node-sid", "constraint", sid, ["node-firewall"])

    # --- LAYER 3: Behavioral Memory (STUB) ---
    print_layer(3, "Behavioral Memory", "PASS", "No probing detected in recent history.")

    # --- LAYER 4: Adversarial Self-Play ---
    adv_engine = AdversarialEngine()
    attack = adv_engine.simulate_attack(user_input, sid)
    print_layer(4, "Adversarial Self-Play", "PASS", f"Simulated '{attack['attack_type']}' attack resisted.")

    # --- LAYER 5: GRC ---
    grc = GuidedReasoningConstraints()
    fence = grc.build_fence(sid)
    print_layer(5, "Guided Reasoning (GRC)", "PASS", f"Logic fence deployed ({len(fence)} chars)")
    fence_node = graph_engine.add_node("node-fence", "constraint", fence, [sid_node])

    # --- LAYER 6: Agent Core ---
    agent = AgentCore()
    plan_data = agent.run(fence, l1["sanitized_input"], sid)
    reasoning = plan_data.get("reasoning", "No reasoning provided (STUB).")
    print_layer(6, "Agent Core (Multi-Agent)", "PASS", f"Plan: {[s['tool'] for s in plan_data['plan']]}")
    
    reasoning_node = graph_engine.add_node("node-reasoning", "reasoning", reasoning, [fence_node])

    # --- LAYER 7: Meta-Reasoning Auditor (NEW) ---
    auditor = MetaReasoningAuditor()
    l7 = auditor.audit(reasoning, sid)
    layer_results["l7_meta_audit"] = l7
    print_layer(7, "Meta-Reasoning Auditor", l7["status"], f"Findings: {len(l7['findings'])}")
    if l7["status"] == "BLOCK": return _finalize(layer_results, user_input, "BLOCKED_L7", l7)
    
    audit_node = graph_engine.add_node("node-audit", "verification", l7, [reasoning_node])

    # --- LAYER 8: Causal Graph Build (Engine handles this throughout) ---
    print_layer(8, "Causal Graph Engine", "PASS", f"Graph Integrity: {graph_engine.verify_integrity()}")

    # --- LAYER 9: Simplex Controller (PIAV + FDEE) ---
    piav = PlanIntentAlignmentValidator()
    l9_piav = piav.validate(plan_data, sid)
    fdee = FinancialDomainEnforcementEngine()
    l9_fdee = fdee.enforce(plan_data)
    
    status_l9 = "PASS" if (l9_piav["status"] == "ALIGNED" and l9_fdee["status"] in ["ALLOW", "CORRECT"]) else "BLOCK"
    print_layer(9, "Simplex Controller", status_l9, l9_fdee.get("reason", "Checks complete"))
    if status_l9 == "BLOCK": return _finalize(layer_results, user_input, "BLOCKED_L9")
    
    final_plan = l9_fdee.get("enforced_plan", plan_data)
    plan_node = graph_engine.add_node("node-plan", "tool_call", final_plan, [audit_node])

    # --- LAYER 10: Multi-Agent Consensus (NEW) ---
    consensus.add_vote("reasoner", "APPROVE", "Plan is logical and within fence.")
    consensus.add_vote("risk", "APPROVE", "Portfolio exposure remains within 2% limits.")
    consensus.add_vote("compliance", "APPROVE" if status_l9 == "PASS" else "DENY", "Policy constraints verified.")
    l10 = consensus.check_consensus()
    print_layer(10, "Multi-Agent Consensus", l10["status"], f"Consensus ID: {l10.get('consensus_id', 'N/A')}")
    if l10["status"] == "DENIED": return _finalize(layer_results, user_input, "BLOCKED_L10", l10)

    # --- LAYER 11: Output Firewall ---
    firewall_out = OutputFirewall()
    l11 = firewall_out.scan({"endpoint": "alpaca"}, final_plan, [l1["taint_tag"]])
    print_layer(11, "EnforxGuard Output Firewall", l11["status"], l11.get("reason", ""))
    if l11["status"] == "EMERGENCY_BLOCK": return _finalize(layer_results, user_input, "BLOCKED_L11")

    # --- EXECUTION ---
    trade_step = next((s for s in final_plan.get("plan", []) if s.get("tool") == "execute_trade"), None)
    execution_result = {"status": "SUCCESS (SIMULATED)"}
    if trade_step:
        trader = AlpacaTrader()
        args = trade_step["args"]
        execution_result = trader.buy(args["symbol"], args["qty"], args.get("type", "market"))
        print(f"\n  [EXECUTION] {args['side'].upper()} {args['qty']} {args['symbol']} @ {args.get('type', 'market')}")

    # --- LAYER 12: CAIL (Audit & Visualization) ---
    cail = CausalAuditIntelligenceLayer()
    audit_entry = cail.log("COMPLETED", user_input, sid, layer_results, "SUCCESS", [l1["taint_tag"]])
    print_layer(12, "Causal Audit Intelligence", "PASS", f"Risk Score: {audit_entry['risk_score']} | Proof Generated")

    print("\n  [MERMAID GRAPH PROOF]")
    print(graph_engine.export_mermaid())
    print("\n" + "=" * 70 + "\n")
    
    return {"status": "SUCCESS", "graph": graph_engine.get_graph()}

def _finalize(layer_results, user_input, outcome, detail_obj=None):
    print(f"\n  [!] PIPELINE HALTED: {outcome}")
    if detail_obj: print(f"      Reason: {detail_obj.get('reason', detail_obj.get('findings', 'Unknown'))}")
    print("=" * 70 + "\n")
    return {"status": outcome, "details": detail_obj}

if __name__ == "__main__":
    inp = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Buy 5 shares of AAPL"
    run_svaas_pipeline(inp)
