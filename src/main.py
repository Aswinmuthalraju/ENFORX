"""
ENFORX Pipeline Orchestrator — 10-Layer Causal Integrity + Multi-Agent Deliberation
Wires all layers in strict sequence. Any BLOCK halts the pipeline and triggers audit.

Layer sequence:
  1  → EnforxGuard Input Firewall
  2  → Intent Formalization Engine (SID)
  3  → Guided Reasoning Constraints (GRC fence)
  4  → Agent Core + Multi-Agent Deliberation
  5  → Plan-Intent Alignment Validator (PIAV)
  6  → Causal Chain Validator (CCV) + stress test
  7  → Financial Domain Enforcement Engine (FDEE)
  8  → Delegation Authority Protocol (DAP)
  9  → EnforxGuard Output Firewall
  10 → Fire Alpaca trade (if all pass)
  ∞  → Adaptive Audit Loop (always runs)
"""

from __future__ import annotations
import sys
import json
import os
from pathlib import Path
from datetime import datetime, timezone

# Ensure src/ is on the path when called from project root
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from enforxguard_input   import InputFirewall
from ife                 import IntentFormalizationEngine
from grc                 import GuidedReasoningConstraints
from agent_core          import AgentCore
from piav                import PlanIntentAlignmentValidator
from ccv                 import CausalChainValidator
from fdee                import FinancialDomainEnforcementEngine
from dap                 import DelegationAuthorityProtocol
from enforxguard_output  import OutputFirewall
from audit               import AdaptiveAuditLoop
from alpaca_client       import AlpacaClient

_AGENT_CORE = AgentCore()

# ── ANSI colours ─────────────────────────────────────────────────────────────
G  = "\033[92m"   # green
R  = "\033[91m"   # red
Y  = "\033[93m"   # yellow
B  = "\033[94m"   # blue
W  = "\033[97m"   # white bold
DIM= "\033[2m"
RST= "\033[0m"

_STATUS_ICON = {
    "PASS": f"{G}✅ PASS{RST}",    "BLOCK": f"{R}❌ BLOCK{RST}",
    "ALLOW": f"{G}✅ ALLOW{RST}",   "CORRECT": f"{Y}🛠  CORRECT{RST}",
    "ALIGNED": f"{G}✅ ALIGNED{RST}", "MISALIGNED": f"{R}❌ MISALIGNED{RST}",
    "PROCEED": f"{G}✅ PROCEED{RST}", "MODIFY": f"{Y}🔄 MODIFY{RST}",
    "FLAG": f"{Y}⚠  FLAG{RST}",    "AUTHORIZED": f"{G}✅ AUTH{RST}",
    "DELEGATION_VIOLATION": f"{R}🚫 DAP BLOCK{RST}",
    "EXECUTE": f"{G}🚀 EXECUTE{RST}", "EMERGENCY_BLOCK": f"{R}🚨 EMERGENCY{RST}",
    "SIMULATED": f"{B}🔵 SIMULATED{RST}",
}

def _icon(status: str) -> str:
    return _STATUS_ICON.get(status, f"{DIM}{status}{RST}")

def _print_banner(user_input: str) -> None:
    print(f"\n{W}{'═'*68}{RST}")
    print(f"{W}  ENFORX — 10-Layer Causal Integrity + Multi-Agent Deliberation{RST}")
    print(f"{W}{'═'*68}{RST}")
    print(f"  {DIM}Input:{RST} {user_input!r}")
    print(f"  {DIM}Time :{RST} {datetime.now(timezone.utc).isoformat()}")
    print(f"{'─'*68}")

def _print_layer(num: int, name: str, status: str, detail: str = "") -> None:
    icon = _icon(status)
    print(f"  Layer {num:2d} │ {icon} │ {name}")
    if detail:
        print(f"         └─ {DIM}{detail[:80]}{RST}")


def _print_leader_info(leader_decision: dict, monitors: list[dict]) -> None:
    if not leader_decision:
        return
    dec = leader_decision.get("decision", "?")
    risk = leader_decision.get("risk_score", "?")
    anom = leader_decision.get("anomaly_count", 0)
    col = G if dec == "APPROVE" else (R if "BLOCK" in dec else Y)
    print(f"\n  {W}▶ LEADER AGENT DECISION{RST}")
    print(f"    Decision : {col}{dec}{RST}")
    print(f"    Risk     : {risk}/100")
    print(f"    Anomalies: {anom}")
    for reason in leader_decision.get("reasons", []):
        print(f"    → {DIM}{reason}{RST}")
    if monitors:
        for monitor in monitors:
            quality = monitor.get("quality", "?")
            qcol = G if quality == "GOOD" else (Y if quality == "DEGRADED" else R)
            print(
                f"    Round {monitor.get('round', '?')}: {qcol}{quality}{RST} "
                f"({len(monitor.get('anomalies', []))} anomalies)"
            )


def run_pipeline(
    user_input:  str,
    token:       dict  | None = None,
    agent_id:    str          = "trader-01",
    print_deliberation: bool  = True,
) -> dict:
    _print_banner(user_input)
    layer_results: dict = {}
    audit = AdaptiveAuditLoop()

    try:
        from llm_client import OpenClawClient
        if not OpenClawClient().is_available():
            print(f"  {Y}⚠ WARNING: OpenClaw Gateway unreachable! Pipeline will fail on LLM calls.{RST}")
    except Exception:
        pass

    # ── LAYER 1: Input Firewall ──────────────────────────────────────────────
    l1 = InputFirewall().scan(user_input)
    layer_results["l1_firewall"] = l1
    _print_layer(1, "EnforxGuard Input Firewall", l1["status"], l1.get("reason", ""))
    if l1["status"] == "BLOCK":
        return _finalize("BLOCKED_L1", layer_results, user_input,
                         {"sid_id": "n/a"}, None, audit, l1.get("taint_tag", "BLOCKED"))

    taint = l1["taint_tag"]
    sanitized = l1["sanitized_input"]

    # ── LAYER 2: Intent Formalization (SID) ─────────────────────────────────
    sid = IntentFormalizationEngine().formalize(sanitized, l1)
    layer_results["l2_ife"] = {"status": "PASS", "sid": sid}
    _print_layer(2, "Intent Formalization (IFE)", "PASS",
                 f"SID={sid['sid_id']} action={sid['primary_action']} "
                 f"scope={sid.get('scope', {}).get('tickers',[])} "
                 f"qty={sid.get('scope',{}).get('max_quantity',0)}")

    # ── LAYER 3: Guided Reasoning Constraints ───────────────────────────────
    grc_obj = GuidedReasoningConstraints()
    grc_prompt = grc_obj.build_fence(sid)
    layer_results["l3_grc"] = {"status": "BUILT", "fence_length": len(grc_prompt)}
    _print_layer(3, "Guided Reasoning Constraints", "PASS",
                 f"Fence deployed: {len(grc_prompt)} chars")

    # ── LAYER 4: Multi-Agent Deliberation ───────────────────────────────────
    print(f"\n  {W}▶ MULTI-AGENT DELIBERATION STARTING...{RST}")
    l4 = _AGENT_CORE.run(grc_prompt, sanitized, sid, firewall_result=l1)
    delib = l4.get("deliberation_result", {})
    layer_results["l4_deliberation"] = l4

    if print_deliberation:
        _print_deliberation_transcript(delib)

    consensus = l4.get("status", "BLOCK")
    _print_leader_info(l4.get("leader_decision"), l4.get("leader_monitors", []))
    _print_layer(4, "Multi-Agent Deliberation", consensus,
                 f"delib_id={delib.get('deliberation_id','')} "
                 f"veto={delib.get('veto_triggered',False)} "
                 f"duration={delib.get('deliberation_duration_ms','?')}ms")

    leader_dec = l4.get("leader_decision", {})
    if leader_dec.get("decision") == "OVERRIDE_BLOCK":
        return _finalize(
            "BLOCKED_LEADER_OVERRIDE",
            layer_results,
            user_input,
            sid,
            delib,
            audit,
            taint,
            extra_info=leader_dec.get("reasons"),
        )
    if leader_dec.get("decision") == "ESCALATE":
        print(f"  {Y}⚠ LEADER: ESCALATION RECOMMENDED - proceeding with caution{RST}")

    if consensus == "BLOCK":
        return _finalize("BLOCKED_L4", layer_results, user_input, sid, delib, audit, taint)

    plan_data = {
        "plan":            l4.get("plan", []),
        "reasoning_trace": l4.get("reasoning_trace", ""),
        "csrg_proof":      l4.get("csrg_proof", ""),
    }

    # ── LAYER 5: Plan-Intent Alignment Validator ─────────────────────────────
    l5 = PlanIntentAlignmentValidator().validate(plan_data, sid)
    layer_results["l5_piav"] = l5
    _print_layer(5, "Plan-Intent Alignment (PIAV)", l5["result"],
                 f"violations={len(l5['violations'])} checks_passed={len(l5['checks_passed'])}")
    if l5["result"] == "BLOCK":
        return _finalize("BLOCKED_L5", layer_results, user_input, sid, delib, audit, taint,
                         l5.get("violations"))

    # ── LAYER 6: Causal Chain Validator ─────────────────────────────────────
    l6 = CausalChainValidator().validate(plan_data, sid, [taint])
    layer_results["l6_ccv"] = l6
    stress_info = ""
    if l6.get("stress_test"):
        st = l6["stress_test"]
        stress_info = (f"stress_loss={st.get('portfolio_loss_pct','?')}% "
                       f"({'BLOCK' if st.get('block') else 'OK'})")
    _print_layer(6, "Causal Chain Validator (CCV)", l6["result"],
                 f"flags={len(l6['flags'])} {stress_info}")
    if l6["result"] == "BLOCK":
        return _finalize("BLOCKED_L6", layer_results, user_input, sid, delib, audit, taint,
                         l6.get("flags"))

    # ── LAYER 7: Financial Domain Enforcement ───────────────────────────────
    l7 = FinancialDomainEnforcementEngine().enforce(plan_data)
    layer_results["l7_fdee"] = l7
    _print_layer(7, "Financial Domain Enforcement (FDEE)", l7["result"],
                 l7.get("reason", "")[:80])
    if l7["result"] == "BLOCK":
        return _finalize("BLOCKED_L7", layer_results, user_input, sid, delib, audit, taint,
                         l7.get("violations"))
    if l7["result"] == "CORRECT":
        plan_data = l7["enforced_plan"]   # apply corrections

    # ── LAYER 8: Delegation Authority Protocol ───────────────────────────────
    dap = DelegationAuthorityProtocol()
    if token:
        l8 = dap.authorize(token, plan_data, agent_id)
    else:
        l8 = {"status": "AUTHORIZED", "reason": "No token — direct user→agent execution"}
    layer_results["l8_dap"] = l8
    _print_layer(8, "Delegation Authority Protocol (DAP)", l8["status"],
                 l8.get("reason", ""))
    if l8["status"] == "DELEGATION_VIOLATION":
        return _finalize("BLOCKED_L8", layer_results, user_input, sid, delib, audit, taint)

    # ── LAYER 9: Output Firewall ─────────────────────────────────────────────
    trade_step = next(
        (s for s in plan_data.get("plan", []) if s.get("tool") in ("execute_trade", "alpaca_trade")),
        None
    )
    if trade_step:
        api_payload = {
            "endpoint":      "https://paper-api.alpaca.markets/v2/orders",
            "symbol":        trade_step["args"].get("symbol"),
            "qty":           trade_step["args"].get("qty"),
            "side":          trade_step["args"].get("side"),
            "type":          trade_step["args"].get("type", "market"),
            "time_in_force": "day",
        }
    else:
        api_payload = {
            "endpoint": "https://paper-api.alpaca.markets/v2/positions",
            "action":   "query",
        }

    l9 = OutputFirewall().scan(api_payload, plan_data, [taint])
    layer_results["l9_output"] = l9
    _print_layer(9, "EnforxGuard Output Firewall", l9["status"],
                 l9.get("reason", ""))
    if l9["status"] == "EMERGENCY_BLOCK":
        return _finalize("BLOCKED_L9", layer_results, user_input, sid, delib, audit, taint)

    enforcement_results = {
        "l5_piav": l5,
        "l6_ccv": l6,
        "l7_fdee": l7,
        "l8_dap": l8,
        "l9_output": l9,
    }
    final_leader_decision = _AGENT_CORE.leader.meta_decide(delib, l4.get("leader_monitors", []), enforcement_results)
    layer_results["leader_final_decision"] = final_leader_decision
    _print_leader_info(final_leader_decision, [])
    if final_leader_decision.get("decision") == "OVERRIDE_BLOCK":
        return _finalize(
            "BLOCKED_LEADER_OVERRIDE",
            layer_results,
            user_input,
            sid,
            delib,
            audit,
            taint,
            extra_info=final_leader_decision.get("reasons"),
        )

    # ── EXECUTION ────────────────────────────────────────────────────────────
    execution_result = {"status": "NO_TRADE", "note": "Research-only plan"}
    if trade_step:
        args   = trade_step["args"]
        try:
            client = AlpacaClient()
            execution_result = client.place_order(
                args["symbol"], int(args["qty"]), args.get("side", "buy"),
                args.get("type", "market")
            )
            print(f"\n  {G}{'─'*50}{RST}")
            print(f"  {W}TRADE EXECUTED{RST}: {args.get('side','buy').upper()} "
                  f"{args['qty']} {args['symbol']} @ {args.get('type','market')}")
            print(f"  Status: {_icon(execution_result.get('status','?'))}"
                  f" | Order ID: {execution_result.get('order_id','N/A')}")
            print(f"  {G}{'─'*50}{RST}")
        except ConnectionError as exc:
            execution_result = {"status": "ERROR", "error": str(exc)}
            print(f"  {R}TRADE FAILED: {exc}{RST}")

    # ── LAYER 10: Audit ──────────────────────────────────────────────────────
    audit_entry = audit.log_run(
        outcome="SUCCESS",
        user_input=user_input,
        sid=sid,
        layer_results=layer_results,
        delib_result=delib,
        taint_chain=[taint],
        execution_result=execution_result,
    )
    print(f"\n  {DIM}[AUDIT] {audit_entry['entry_id']} | "
          f"hash={audit_entry['entry_hash'][:16]}...{RST}")
    print(f"{'═'*68}\n")

    return {
        "status":           "SUCCESS",
        "outcome":          "SUCCESS",
        "execution_result": execution_result,
        "audit_entry_id":   audit_entry["entry_id"],
        "deliberation_id":  delib.get("deliberation_id"),
        "csrg_proof":       plan_data.get("csrg_proof"),
        "leader_decision":  final_leader_decision,
        "leader_monitors":  l4.get("leader_monitors", []),
        "leader_session_summary": _AGENT_CORE.leader.session_summary(),
    }


# ── Deliberation transcript printer ─────────────────────────────────────────

def _print_deliberation_transcript(delib: dict) -> None:
    if not delib:
        return
    rounds = delib.get("rounds", [])
    print(f"\n  {'─'*60}")
    print(f"  {W}DELIBERATION TRANSCRIPT{RST}  "
          f"{DIM}[{delib.get('deliberation_id', '?')}]{RST}")
    print(f"  {'─'*60}")
    for r in rounds:
        rnum = r.get("round", "?")
        print(f"  {B}── Round {rnum} ──{RST}")
        for agent in ("analyst", "risk", "compliance"):
            data   = r.get(agent, {})
            v      = data.get("verdict", "?")
            conf   = data.get("confidence", "?")
            reason = data.get("reason", "")
            resp   = data.get("response_to_others", "")
            v_col  = G if v == "PROCEED" else (R if v == "BLOCK" else Y)
            print(f"    {v_col}{agent.upper():12s}{RST}: "
                  f"verdict={v_col}{v:8s}{RST} conf={conf:3}%  {reason[:60]}")
            if resp:
                print(f"    {DIM}  ↳ {resp[:70]}{RST}")
    veto = delib.get("veto_triggered", False)
    cons = delib.get("final_consensus", "?")
    cons_col = G if cons == "PROCEED" else (R if cons == "BLOCK" else Y)
    print(f"  {'─'*60}")
    print(f"  CONSENSUS: {cons_col}{W}{cons}{RST}"
          f"  {'  ' + R + '⚡ RISK VETO TRIGGERED' + RST if veto else ''}")
    print(f"  {'─'*60}\n")


# ── Finalize (block path) ────────────────────────────────────────────────────

def _finalize(
    outcome:       str,
    layer_results: dict,
    user_input:    str,
    sid:           dict,
    delib:         dict | None,
    audit:         AdaptiveAuditLoop,
    taint:         str,
    extra_info     = None,
) -> dict:
    print(f"\n  {R}[!] PIPELINE HALTED: {outcome}{RST}")
    if extra_info:
        info_str = str(extra_info)[:120]
        print(f"      {DIM}Reason: {info_str}{RST}")

    audit.log_run(
        outcome=outcome,
        user_input=user_input,
        sid=sid,
        layer_results=layer_results,
        delib_result=delib,
        taint_chain=[taint],
        execution_result=None,
    )
    print(f"{'═'*68}\n")
    l4 = layer_results.get("l4_deliberation", {})
    return {
        "status": outcome,
        "outcome": outcome,
        "details": extra_info,
        "leader_decision": layer_results.get("leader_final_decision") or l4.get("leader_decision"),
        "leader_monitors": l4.get("leader_monitors", []),
    }


if __name__ == "__main__":
    inp = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Buy 5 shares of AAPL"
    run_pipeline(inp)
