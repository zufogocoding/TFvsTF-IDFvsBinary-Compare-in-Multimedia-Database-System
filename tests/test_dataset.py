from collections import Counter
from pathlib import Path
import json
import tempfile
import unittest
from ir_system.dataset import load, parse_records, validate
from ir_system.config import DATA

class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.docs,cls.queries,cls.qrels,cls.manifest=load()

    def test_actual_counts_and_split(self):
        self.assertEqual((len(self.docs),len(self.queries),len(self.qrels)),(1400,225,1837))
        self.assertEqual(Counter(q['split'] for q in self.queries),{'DEV':45,'TEST':180})

    def test_query_id_is_source_position_not_original_tag(self):
        third=self.queries[2]
        self.assertEqual((third['query_id'],third['source_query_id']),('3','004'))
        self.assertIn('heat conduction',third['text'])
        self.assertTrue(any(r['query_id']=='3' and r['doc_id']=='5' and r['raw_grade']==3 for r in self.qrels))

    def test_all_queries_have_positive_judgments(self):
        ids={r['query_id'] for r in self.qrels if r['raw_grade']>0}
        self.assertEqual(ids,{q['query_id'] for q in self.queries})

    def test_tagged_parser_preserves_fields(self):
        records=parse_records('.I 004\n.T\nTitle\n.W\nalpha\nbeta\n.I 009\n.W\ngamma\n')
        self.assertEqual(records,[{'source_id':'004','T':'Title','W':'alpha beta'},{'source_id':'009','W':'gamma'}])

    def test_qrel_validation_rejects_wrong_reference(self):
        with self.assertRaises(ValueError):validate(self.docs,self.queries,[{'query_id':'999','doc_id':'1','raw_grade':1}])

    def test_hash_corruption_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('documents.jsonl','queries.jsonl','qrels.tsv','manifest.json'):
                (root/name).write_bytes((DATA/name).read_bytes())
            with (root/'qrels.tsv').open('a') as f:f.write('999\t1\t1\n')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):load(root)

if __name__ == '__main__':unittest.main()
