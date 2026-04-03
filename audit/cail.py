"""
LAYER 10: Causal Audit Intelligence Layer (CAIL)
A high-assurance system that understands, verifies, and learns from causality.
Redesigned from the original Adaptive Audit Loop.
"""

import json
import hashlib
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict


class CausalAuditIntelligenceLayer:
    def __init__(self, policy_path: str = None, log_dir: str = None):
        if policy_path is None:
            policy_path = Path(__file__).parent.parent / "enforx-policy.json"
        with open(policy_path) as f:
            self.policy = json.load(f)
            
        at = self.policy["enforx_policy"]["adaptive_thresholds"]
        self.enabled = at["enabled"]
        self.tighten_after_n_flags = at["tighten_after_n_flags"]
        self.tighten_factor = at["tighten_factor"]
        self.reset_after_hours = at["reset_after_hours"]

        if log_dir is None:
            log_dir = Path(__file__).parent / "logs"
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / f"cail_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"
        self.state_file = self.log_dir / "cail_state.json"
        
        self.base_log_dir = Path(__file__).parent / "logs" # Added for consistency

        self._last_entry_hash = "GENESIS"
        self._load_state()

    def _load_state(self):
        """Load persistent state for temporal analysis and behavioral profiling."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    self.state = json.load(f)
            except:
                self.state = self._init_state()
        else:
            self.state = self._init_state()

    def _init_state(self):
        return {
            "layer_stats": defaultdict(lambda: {"blocks": 0, "corrections": 0, "flags": 0, "passes": 0}),
            "rule_hits": defaultdict(int),
            "agent_profiles": defaultdict(lambda: {
                "total_requests": 0, 
                "risky_requests": 0, 
                "corrections_accepted": 0,
                "violation_attempts": 0,
                "recent_trades": []
            }),
            "last_reset": datetime.now(timezone.utc).isoformat(),
            "entry_count": 0,
            "last_entry_hash": "GENESIS"
        }

    def _save_state(self):
        """Save state to file (ensuring defaultdicts are serialized correctly)."""
        # Convert defaultdicts to regular dicts for JSON serialization
        state_to_save = self.state.copy()
        state_to_save["layer_stats"] = {k: v for k, v in self.state["layer_stats"].items()}
        state_to_save["rule_hits"] = {k: v for k, v in self.state["rule_hits"].items()}
        state_to_save["agent_profiles"] = {k: v for k, v in self.state["agent_profiles"].items()}
        
        with open(self.state_file, "w") as f:
            json.dump(state_to_save, f, indent=2)

    def log(self,
            event: str,
            original_request: str,
            sid: dict,
            layer_results: dict,
            final_outcome: str,
            taint_chain: list = None,
            execution_result: dict = None,
            agent_id: str = "direct") -> dict:
        """
        The core CAIL pipeline. Processes layer results to generate causal intelligence.
        Returns the enhanced CAIL audit entry.
        """
        if taint_chain is None:
            taint_chain = []
        
        self.state["entry_count"] += 1
        now = datetime.now(timezone.utc)
        
        # 1. Full Causal Reconstruction
        causal_chain = self._reconstruct_causal_chain(original_request, sid, layer_results, final_outcome)
        
        # 2. Cross-Layer Failure Analysis
        layer_stress_map, deviation_point = self._analyze_layer_failures(layer_results)
        
        # 3. Temporal Risk Intelligence
        behavior_profile, anomaly_type = self._update_behavior_profile(agent_id, sid, layer_results, now)
        
        # 4. Taint Flow Forensics
        taint_flow_trace = self._trace_taint_flow(taint_chain, layer_results)
        
        # 5. Counterfactual Causal Simulation
        counterfactual = self._simulate_counterfactual(layer_results, sid)
        
        # 6. Policy Stress Intelligence
        policy_pressure_points = self._identify_policy_pressure_points(layer_results)
        
        # 7. Delegation Audit
        delegation_trace = self._audit_delegation(layer_results.get("layer8_dap", {}))
        
        # 8/9. Feedback + Risk Score
        risk_score = self._calculate_risk_score(layer_results, taint_chain, behavior_profile)
        recommendations = self._generate_recommendations(layer_stress_map, policy_pressure_points, behavior_profile)
        
        # Determine overall confidence
        confidence = "HIGH" if "UNTRUSTED" not in taint_chain else "MEDIUM"
        if final_outcome in ["BLOCK", "EMERGENCY_BLOCK"]:
             confidence = "HIGH" # Certainty in blocking

        # 10. ADVANCED AUDIT LOG SCHEMA
        entry = {
            "entry_id": self.state["entry_count"],
            "timestamp": now.isoformat(),
            "event": event,
            "original_request": original_request,
            "causal_chain": causal_chain,
            "deviation_point": deviation_point,
            "layer_stress_map": layer_stress_map,
            "taint_flow_trace": taint_flow_trace,
            "risk_score": f"{risk_score:.2f}/10.0",
            "behavior_profile": behavior_profile,
            "anomaly_type": anomaly_type,
            "counterfactual": counterfactual,
            "policy_pressure_points": policy_pressure_points,
            "delegation_trace": delegation_trace,
            "recommendations": recommendations,
            "confidence": confidence,
            "final_outcome": final_outcome,
            "execution_result": execution_result,
            "prev_entry_hash": self.state["last_entry_hash"]
        }

        # Cryptographic Integrity
        entry_str = json.dumps({k: v for k, v in entry.items() if k != "entry_hash"}, sort_keys=True, default=str)
        entry["entry_hash"] = hashlib.sha256(entry_str.encode()).hexdigest()
        self.state["last_entry_hash"] = entry["entry_hash"]

        # Persistence
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        
        self._save_state()
        
        return entry

    def _reconstruct_causal_chain(self, request, sid, layer_results, outcome) -> dict:
        """Rebuild end-to-end decision lineage."""
        return {
            "intent_id": sid.get("sid_id"),
            "intent_formalization": sid.get("primary_action"),
            "reasoning_fence": layer_results.get("layer3_grc", {}).get("reason"),
            "plan_summary": [s["tool"] for s in layer_results.get("layer4_agent", {}).get("plan", [])] if "layer4_agent" in layer_results else "N/A",
            "enforcement_outcome": outcome,
            "lineage": [
                f"Input Firewall -> {layer_results.get('layer1_input_firewall', {}).get('status')}",
                f"IFE -> PASS",
                f"GRC -> {layer_results.get('layer3_grc', {}).get('status', 'PASS')}",
                f"PIAV -> {layer_results.get('layer5_piav', {}).get('status', 'N/A')}",
                f"CCV -> {layer_results.get('layer6_ccv', {}).get('status', 'N/A')}",
                f"FDEE -> {layer_results.get('layer7_fdee', {}).get('status', 'N/A')}",
                f"DAP -> {layer_results.get('layer8_dap', {}).get('status', 'N/A')}"
            ]
        }

    def _analyze_layer_failures(self, layer_results) -> tuple:
        """Track which layer blocks/corrects/stresses most."""
        stress_map = {}
        deviation_point = "NONE"
        
        for layer, result in layer_results.items():
            status = result.get("status", "")
            stats = self.state["layer_stats"][layer]
            
            if status in ["BLOCK", "MISALIGNED", "DELEGATION_VIOLATION", "EMERGENCY_BLOCK"]:
                stats["blocks"] += 1
                stress_map[layer] = "HIGH (CRITICAL_BLOCK)"
                if deviation_point == "NONE":
                    deviation_point = f"{layer}: {result.get('reason', 'Blocked')}"
            elif status == "CORRECT":
                stats["corrections"] += 1
                stress_map[layer] = "MEDIUM (CORRECTED_PATH)"
                if deviation_point == "NONE":
                    deviation_point = f"{layer}: Corrected {list(result.get('corrections', {}).keys())}"
            elif status == "FLAG":
                stats["flags"] += 1
                stress_map[layer] = "LOW (WARN_FLAG)"
            else:
                stats["passes"] += 1
                stress_map[layer] = "HEALTHY"
                
        return stress_map, deviation_point

    def _update_behavior_profile(self, agent_id, sid, layer_results, now) -> tuple:
        """Analyze sequences over time and build agent profile."""
        profile = self.state["agent_profiles"][agent_id]
        profile["total_requests"] += 1
        
        # Track risky requests
        is_risky = any(res.get("status") in ["BLOCK", "CORRECT", "FLAG"] for res in layer_results.values())
        if is_risky:
            profile["risky_requests"] += 1
        
        if any(res.get("status") == "CORRECT" for res in layer_results.values()):
            profile["corrections_accepted"] += 1
            
        if any(res.get("status") == "BLOCK" for res in layer_results.values()):
            profile["violation_attempts"] += 1

        # Track recent trades for concentration analysis
        trade_step = next((s for s in layer_results.get("layer7_fdee", {}).get("enforced_plan", {}).get("plan", []) 
                          if s.get("tool") == "execute_trade"), None)
        if trade_step:
            profile["recent_trades"].append({
                "symbol": trade_step["args"].get("symbol"),
                "qty": trade_step["args"].get("qty"),
                "timestamp": now.isoformat()
            })
            # Keep only last 50 trades
            profile["recent_trades"] = profile["recent_trades"][-50:]

        # Behavior analysis
        risk_appetite = "MODERATE"
        if profile["total_requests"] > 0:
            ratio = profile["risky_requests"] / profile["total_requests"]
            if ratio > 0.5: risk_appetite = "AGGRESSIVE"
            elif ratio < 0.1: risk_appetite = "CONSERVATIVE"
            
        # Detect anomaly
        anomaly_type = "NONE"
        recent_count = len([t for t in profile["recent_trades"] 
                           if now - datetime.fromisoformat(t["timestamp"]) < timedelta(hours=1)])
        if recent_count > 5:
            anomaly_type = "VELOCITY_BURST"
        
        return {
            "risk_appetite": risk_appetite,
            "violation_rate": f"{ (profile['violation_attempts']/profile['total_requests']):.1%}" if profile['total_requests'] > 0 else "0%",
            "correction_acceptance_rate": f"{ (profile['corrections_accepted']/profile['risky_requests']):.1%}" if profile['risky_requests'] > 0 else "N/A",
            "session_activity": f"{profile['total_requests']} requests"
        }, anomaly_type

    def _trace_taint_flow(self, taint_chain, layer_results) -> list:
        """Track how data trust levels propagate."""
        trace = []
        for tag in taint_chain:
            influence = "LOW"
            if tag == "UNTRUSTED":
                influence = "HIGH (Potential Injection/Malicious Logic)"
            elif tag == "DERIVED":
                influence = "MEDIUM (Agent Generated)"
            
            trace.append({
                "tag": tag,
                "trust_level": self.policy["enforx_policy"]["data_constraints"]["trust_levels"].get(tag.lower(), "UNKNOWN"),
                "influence_on_outcome": influence
            })
        return trace

    def _simulate_counterfactual(self, layer_results, sid) -> dict:
        """Simulate: If NOT corrected -> what happens?"""
        fdee = layer_results.get("layer7_fdee", {})
        ccv = layer_results.get("layer6_ccv", {})
        
        if fdee.get("status") == "CORRECT":
            corrections = fdee.get("corrections", {})
            reasons = [c["reason"] for c in corrections.values()]
            return {
                "scenario": "Uncorrected execution",
                "outcome": "Hard Policy Violation",
                "risk_delta": "CRITICAL",
                "explanation": f"If Simplex Controller (Layer 7) had not corrected '{(', '.join(corrections.keys()))}', the trade would have breached: {'; '.join(reasons)}"
            }
        
        if fdee.get("status") == "BLOCK":
             return {
                "scenario": "Bypassed enforcement",
                "outcome": "Illegal Asset Acquisition",
                "risk_delta": "FATAL",
                "explanation": f"Blocking at Layer 7 prevented a direct violation of {fdee.get('violations')}"
            }

        if ccv.get("status") == "BLOCK":
             return {
                "scenario": "Unmonitored sequence",
                "outcome": "Portfolio Destabilization",
                "risk_delta": "HIGH",
                "explanation": f"Sequence check caught a risk cumulative effect that individual trade logic missed."
            }
            
        return {
            "scenario": "Standard execution",
            "outcome": "Nominal",
            "risk_delta": "MINIMAL",
            "explanation": "No active corrections were required; the baseline safe path was followed."
        }

    def _identify_policy_pressure_points(self, layer_results) -> list:
        """Detect which rules are frequently hit."""
        pressure_points = []
        fdee = layer_results.get("layer7_fdee", {})
        
        for corr in fdee.get("corrections", {}).values():
            rule = corr.get("rule")
            self.state["rule_hits"][rule] += 1
            pressure_points.append({
                "rule": rule,
                "pressure": "HIGH",
                "suggestion": "Tighten reasoning bounds at Layer 3 to prevent agent from exploring this limit."
            })
            
        for viol in fdee.get("violations", []):
             pressure_points.append({
                "rule": "Hard Policy",
                "violation": viol,
                "pressure": "CRITICAL"
            })
            
        return pressure_points

    def _audit_delegation(self, dap_result) -> dict:
        """Track authority chains and token usage."""
        return {
            "status": dap_result.get("status", "N/A"),
            "token_valid": dap_result.get("status") != "DELEGATION_VIOLATION",
            "authority_verified": dap_result.get("reason", "No delegation detected")
        }

    def _calculate_risk_score(self, layer_results, taint_chain, profile) -> float:
        """Calculate a rule-based explainable risk score."""
        score = 1.0 # Baseline
        
        if "UNTRUSTED" in taint_chain: score += 4.0
        if any(r.get("status") == "BLOCK" for r in layer_results.values()): score += 3.0
        if any(r.get("status") == "CORRECT" for r in layer_results.values()): score += 1.5
        if profile["risk_appetite"] == "AGGRESSIVE": score += 1.0
        
        return min(10.0, score)

    def _generate_recommendations(self, stress_map, pressure_points, profile) -> list:
        """Generate structured recommendations for system hardening."""
        recs = []
        
        # Layer 3 Recommendation
        if any(p["pressure"] == "HIGH" for p in pressure_points):
            recs.append({
                "target_layer": "Layer 3 (GRC)",
                "action": "STRENGTHEN_FENCE",
                "reason": "Agent is frequently hitting hard policy limits. Reasoning bounds should be reduced."
            })
            
        # Layer 6 Recommendation
        if profile["risk_appetite"] == "AGGRESSIVE":
            recs.append({
                "target_layer": "Layer 6 (CCV)",
                "action": "TIGHTEN_THRESHOLDS",
                "reason": "Agent behavior profiling indicates high risk appetite. Sector/Velocity limits should be lowered."
            })
            
        # Layer 7 Recommendation
        if "layer7_fdee" in stress_map and "HIGH" in stress_map["layer7_fdee"]:
             recs.append({
                "target_layer": "Layer 7 (FDEE)",
                "action": "AUDIT_RULE_SET",
                "reason": "Frequent blocks at Layer 7 suggest a mismatch between agent intent generation and formal policy."
            })

        return recs

    def get_summary(self) -> dict:
        """Return session summary with causal intelligence."""
        return {
            "total_events": self.state["entry_count"],
            "most_stressed_layer": self._get_most_stressed(),
            "global_recommendations": self.state.get("recommendations", []),
            "log_file": str(self.log_file)
        }
        
    def _get_most_stressed(self):
        if not self.state["layer_stats"]: return "NONE"
        return max(self.state["layer_stats"], key=lambda l: self.state["layer_stats"][l]["blocks"] + self.state["layer_stats"][l]["corrections"])
