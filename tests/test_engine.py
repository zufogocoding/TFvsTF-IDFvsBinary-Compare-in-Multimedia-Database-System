import math
import unittest
import numpy as np
from numpy.testing import assert_allclose
from ir_system.engine import RetrievalEngine, tokenize

def document(doc_id, text):
    return {"doc_id": doc_id, "title": "", "body": text}

class WeightingTests(unittest.TestCase):
    def setUp(self):
        self.engine = RetrievalEngine([document("d2", "alpha beta beta"), document("d1", "alpha gamma"), document("d3", "gamma gamma")])

    def test_counts_and_corpus_idf(self):
        e = self.engine
        self.assertEqual(e.counts.shape, (3, 3))
        a,b,g = [e.vocabulary[t] for t in ("alpha", "beta", "gamma")]
        assert_allclose(e.counts.toarray()[:, [a,b,g]], [[1,2,0],[1,0,1],[0,0,2]])
        assert_allclose(e.idf[[a,b,g]], [math.log(3/2), math.log(3), math.log(3/2)])

    def test_binary_tie_break_is_lexical(self):
        ranking = self.engine.search("alpha", "BINARY")["ranking"]
        self.assertEqual([d for d,s in ranking], ["d1", "d2"])
        assert_allclose([s for d,s in ranking], [1/math.sqrt(2)]*2)

    def test_tf_cosine_matches_hand_calculation(self):
        scores = dict(self.engine.search("alpha", "TF")["ranking"])
        self.assertAlmostEqual(scores["d2"], 1/math.sqrt(5))
        self.assertAlmostEqual(scores["d1"], 1/math.sqrt(2))
        self.assertNotIn("d3", scores)

    def test_tfidf_cosine_matches_hand_calculation(self):
        scores = dict(self.engine.search("alpha", "TFIDF")["ranking"])
        a,b = math.log(3/2),math.log(3)
        self.assertAlmostEqual(scores["d2"], a/math.sqrt(a*a+4*b*b))
        self.assertAlmostEqual(scores["d1"], 1/math.sqrt(2))

    def test_query_repetition_is_binary_or_count_as_declared(self):
        e=self.engine;a=e.vocabulary["alpha"];b=e.vocabulary["beta"]
        assert_allclose(e.query_vector("alpha alpha beta","BINARY").toarray()[0,[a,b]], [1/math.sqrt(2)]*2)
        assert_allclose(e.query_vector("alpha alpha beta","TF").toarray()[0,[a,b]], [2/math.sqrt(5),1/math.sqrt(5)])

    def test_zero_idf_query_is_handled_without_nan(self):
        e=RetrievalEngine([document("2","common alpha"),document("10","common beta")])
        self.assertEqual(e.idf[e.vocabulary["common"]],0)
        r=e.search("common","TFIDF")
        self.assertTrue(r["zero_vector"]);self.assertEqual(r["ranking"],[])
        self.assertEqual([d for d,s in e.search("common","BINARY")["ranking"]],["10","2"])

    def test_unknown_and_empty_queries(self):
        for text in ("", "123 ---", "xyznotinvocabulary"):
            for method in ("BINARY","TF","TFIDF"):
                self.assertTrue(self.engine.search(text,method)["zero_vector"])

    def test_all_matrices_are_float64_and_unit_norm(self):
        for matrix in self.engine.matrices.values():
            self.assertEqual(matrix.dtype,np.float64)
            assert_allclose(np.asarray(matrix.multiply(matrix).sum(axis=1)).ravel(),1)

    def test_normalization_is_shared(self):
        self.assertEqual(tokenize("ＡLPHA Beta-123"),["alpha","beta"])

    def test_empty_document_is_retained(self):
        e=RetrievalEngine([document("empty",""),document("full","alpha")])
        self.assertEqual(e.counts.shape[0],2)
        self.assertEqual(e.stats["TF"]["zero_documents"],1)
        self.assertEqual(e.search("alpha","TF")["ranking"],[("full",1.0)])

if __name__ == "__main__": unittest.main()
