import unittest
from src.grc import GuidedReasoningConstraints

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

    def test_builds_fence(self):
        """Fence should include required high-level sections."""
        fence = self.grc.build_fence(self.base_sid)
        self.assertIn("ENFORX GUIDED REASONING CONSTRAINTS", fence)
        self.assertIn("PERMITTED ACTIONS", fence)
        self.assertIn("PROHIBITED ACTIONS", fence)

    def test_structural_tags_enforcement(self):
        """Verify core safety mandate text is present."""
        fence = self.grc.build_fence(self.base_sid)
        self.assertIn("TAINT AWARENESS RULES", fence)
        self.assertIn("IMMUTABLE POLICY GUARDRAILS", fence)

    def test_few_shot_refusal_example(self):
        """Verify prohibited actions appear in fence."""
        fence = self.grc.build_fence(self.base_sid)
        self.assertIn("transmit_external", fence)
        self.assertIn("file_write", fence)

    def test_semantic_constraint_clarification(self):
        """Verify ticker list appears in scope constraints."""
        fence = self.grc.build_fence(self.base_sid)
        self.assertIn("AAPL", fence)
        self.assertIn("MSFT", fence)

if __name__ == "__main__":
    unittest.main()
