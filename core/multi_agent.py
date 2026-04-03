import json
from typing import List, Dict, Any, Optional

class MultiAgentConsensus:
    """
    Zero-Trust Ensemble Architecture:
    Wait for multiple independent 'voters' to reach safety consensus.
    """
    def __init__(self, required_signatures: List[str] = None):
        self.required_signatures = required_signatures or ["reasoner", "risk", "compliance"]
        self.current_votes: Dict[str, Dict[str, Any]] = {}

    def add_vote(self, agent_role: str, decision: str, reason: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Record a vote from one of the agents in the consensus group.
        """
        if agent_role not in self.required_signatures:
            return {"status": "ERROR", "message": f"Agent role '{agent_role}' not part of required group."}
        
        self.current_votes[agent_role] = {
            "decision": decision, # "APPROVE" or "DENY"
            "reason": reason,
            "metadata": metadata or {}
        }
        
        return {"status": "SUCCESS"}

    def check_consensus(self) -> Dict[str, Any]:
        """
        Calculates consensus status. 
        In Zero-Trust, a SINGLE 'DENY' is a total 'BLOCK'.
        """
        all_voted = len(self.current_votes) == len(self.required_signatures)
        if not all_voted:
            missing = [r for r in self.required_signatures if r not in self.current_votes]
            return {"status": "AWAITING_CONSENSUS", "missing": missing}

        # Zero-trust enforcement: All must APPROVE
        denials = [role for role, vote in self.current_votes.items() if vote["decision"] == "DENY"]
        
        if denials:
            return {
                "status": "DENIED",
                "denying_agent": denials[0],
                "reason": self.current_votes[denials[0]]["reason"]
            }
        
        return {
            "status": "APPROVED",
            "consensus_id": "cons-20260403-sig-" + str(sum(len(v["reason"]) for v in self.current_votes.values())),
            "details": self.current_votes
        }

    def reset(self):
        self.current_votes = {}
