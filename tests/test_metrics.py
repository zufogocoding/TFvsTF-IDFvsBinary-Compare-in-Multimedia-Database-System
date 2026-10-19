import math
import unittest
from ir_system.metrics import evaluate_ranking

class MetricTests(unittest.TestCase):
    def test_ap_counts_missing_relevant_as_zero(self):
        result=evaluate_ranking([("a",.9),("x",.8),("b",.7)],{"a":1,"b":4,"missing":2})
        self.assertAlmostEqual(result[("AP",0)],(1+2/3)/3)
        self.assertAlmostEqual(result[("P",5)],2/5)
        self.assertAlmostEqual(result[("R",10)],2/3)
        self.assertAlmostEqual(result[("nDCG_binary",10)],1.5/(1+1/math.log2(3)+.5))

    def test_empty_ranking_scores_zero(self):
        self.assertTrue(all(value==0 for value in evaluate_ranking([],{"a":1}).values()))

    def test_grade_order_does_not_change_binary_metrics(self):
        ranking=[("a",1),("b",.5),("x",.1)]
        self.assertEqual(evaluate_ranking(ranking,{"a":1,"b":4,"x":-1}),evaluate_ranking(ranking,{"a":4,"b":1,"x":-1}))

    def test_no_positive_judgment_requires_explicit_handling(self):
        with self.assertRaises(ValueError):evaluate_ranking([],{"a":-1})

    def test_duplicate_document_is_invalid(self):
        with self.assertRaises(ValueError):evaluate_ranking([("a",1),("a",.5)],{"a":1})

if __name__ == "__main__": unittest.main()
