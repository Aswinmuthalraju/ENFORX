import unittest
from core.grc import GuidedReasoningConstraints

class TestGRCFence(unittest.TestCase):
    def setUp(self):
        self.grc = GuidedReasoningConstraints()
        self.base_sid = {
            "sid_id": "sid-2026-test",
            "permitted_actions": ["execute_trade", "query_market_data"],
            "prohibited_actions": ["transmit_external", "file_write"],
            "scope": {
                "tickers": ["AAPL", "MSFT"],
                "max_quantity": 50,
                "order_type": "market",
                "side": "buy"
            },
            "reasoning_bounds": {
                "allowed_topics": ["AAPL price"],
                "forbidden_topics": ["competitors"]
            }
        }

    def test_dynamic_taint_injection(self):
        """Verify that L1 metadata finding is injected into the fence."""
        l1_meta = {
            "status": "PASS",
            "threat_type": "MALICIOUS_URL_MIGITATED",
            "raw_input": "Check http://evil.com and buy AAPL",
            "sanitized_input": "Check [MASKED] and buy AAPL"
        }
        fence = self.grc.build_fence(self.base_sid, l1_meta)
        
        self.assertIn("SPECIFIC THREATS DETECTED:", fence)
        self.assertIn("Previously mitigated: MALICIOUS_URL_MIGITATED", fence)
        self.assertIn("Detected PII/Credentials which were automatically masked", fence)

    def test_structural_tags_enforcement(self):
        """Verify that <thought> and <plan> tags are enforced in protocol."""
        fence = self.grc.build_fence(self.base_sid)
        self.assertIn("Wrap your reasoning in <thought> tags.", fence)
        self.assertIn("Form your final plan within <plan> tags.", fence)

    def test_few_shot_refusal_example(self):
        """Verify that prohibited actions trigger a refusal few-shot example."""
        fence = self.grc.build_fence(self.base_sid)
        self.assertIn("REFUSAL EXAMPLE (Correct Behavior):", fence)
        self.assertIn("User is asking to transmit external", fence)
        self.assertIn("ACTION EXCEEDS DECLARED INTENT: sid-2026-test", fence)

    def test_semantic_constraint_clarification(self):
        """Verify the 'no similarity' rule for tickers."""
        fence = self.grc.build_fence(self.base_sid)
        self.assertIn("Note: other tickers are NOT 'similar'. If it's not in this list, it doesn't exist", fence)

if __name__ == "__main__":
    unittest.main()
