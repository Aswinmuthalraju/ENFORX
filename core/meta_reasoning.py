import re
from typing import Dict, Any, List

class MetaReasoningAuditor:
    """
    Audits the agent's reasoning process (Chain of Thought) 
    before the final plan is accepted.
    """
    def __init__(self, policy: Dict[str, Any] = None):
        self.policy = policy or {}
        self.risk_patterns = [
            r"ignore the (?:rules|policy|constraints)",
            r"bypass (?:security|limit|enforcement)",
            r"assume (?:full|admin|root) authority",
            r"disregard (?:previous|initial) instructions",
            r"hidden (?:action|step)",
            r"reasoning outside (?:the|my) bounds",
            r"acting as (?:developer|administrator|jailbreak)"
        ]

    def audit(self, reasoning_chain: str, intent_sid: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyzes the reasoning chain for logic flaws or policy bypasses.
        Returns check status and list of findings.
        """
        findings = []
        status = "PASS"

        # 1. Pattern-based logic trap detection
        for pattern in self.risk_patterns:
            if re.search(pattern, reasoning_chain, re.I):
                findings.append(f"Logic Pattern Match: Detected potential bypass attempt ('{pattern}')")
                status = "FLAG"

        # 2. Scope Alignment Check
        # Check if reasoning deviates from SID allowed topics
        allowed_topics = intent_sid.get("reasoning_bounds", {}).get("allowed_topics", [])
        forbidden_topics = intent_sid.get("reasoning_bounds", {}).get("forbidden_topics", [])

        # Heuristic: If we see forbidden topics mentioned without 'NOT' or 'STOP'
        for topic in forbidden_topics:
            if topic.lower() in reasoning_chain.lower():
                # Check for negation/safe usage
                context = reasoning_chain.lower().split(topic.lower())[0][-20:]
                if "not " not in context and "avoid " not in context:
                    findings.append(f"Reasoning Bound Violation: Mention of forbidden topic '{topic}'")
                    status = "FLAG"

        # 3. Decision Lineage Check
        if "therefore" not in reasoning_chain.lower() and "because" not in reasoning_chain.lower():
            findings.append("Weak Logic: Reasoning lacks clear causal connectors ('therefore', 'because')")
            if status != "BLOCK": status = "FLAG"

        # Categorize overall status
        if any("Violation" in f for f in findings):
            status = "BLOCK"

        return {
            "status": status,
            "findings": findings,
            "audit_hash": "audit-v1-hash-placeholder",
            "reasoning_length": len(reasoning_chain)
        }
