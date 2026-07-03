import unittest
import sys
import os

# Add os-ensemble-cr to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'os-ensemble-cr')))

from app import majority_vote, consensus_score

class TestOSOrchestrator(unittest.TestCase):

    def setUp(self):
        self.results = [
            {"invoice_id": "INV-123", "total": "100.00", "tax": "19.00"}, # Model 1
            {"invoice_id": "INV-123", "total": "100.00", "tax": "19.00"}, # Model 2
            {"invoice_id": "INV-999", "total": "100.00", "tax": "7.00"}   # Model 3 (outlier)
        ]

    def test_majority_vote(self):
        # 2 out of 3 agree on INV-123
        self.assertEqual(majority_vote(self.results, "invoice_id"), "INV-123")
        # All 3 agree on total
        self.assertEqual(majority_vote(self.results, "total"), "100.00")
        # 2 out of 3 agree on tax
        self.assertEqual(majority_vote(self.results, "tax"), "19.00")

    def test_consensus_score(self):
        # 2 out of 3 agree = 0.666...
        self.assertAlmostEqual(consensus_score(self.results, "invoice_id"), 2/3)
        # 3 out of 3 agree = 1.0
        self.assertEqual(consensus_score(self.results, "total"), 1.0)
        
    def test_majority_vote_none(self):
        results = [
            {"invoice_id": None},
            {"invoice_id": "123"}
        ]
        self.assertEqual(majority_vote(results, "invoice_id"), "123")
        
        results = [{"invoice_id": None}, {"invoice_id": None}]
        self.assertIsNone(majority_vote(results, "invoice_id"))

if __name__ == '__main__':
    unittest.main()
