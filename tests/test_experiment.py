from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from ir_system.engine import RetrievalEngine
from ir_system.experiment import run_experiment, EXPORT_FILES
from ir_system.storage import Database

class EndToEndTests(unittest.TestCase):
    def test_timing_batches_survive_connection_reopening(self):
        docs=[{'doc_id':'1','title':'','body':'alpha','author':'','bib':''}]
        queries=[{'query_id':'1','source_query_id':'001','text':'alpha','split':'TEST'}]
        qrels=[{'query_id':'1','doc_id':'1','raw_grade':1}]
        manifest={'dataset_id':'unit','name':'unit','language':'en','source_url':'unit','files':{'unit':'hash'}}
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'batches.sqlite3');db.import_dataset(docs,queries,qrels,manifest)
            experiment=db.begin_experiment('unit','TEST',{}, {}, {})
            result={'ranking':[('1',1.0)],'zero_vector':False}
            metrics={('AP',0):1,('nDCG_binary',10):1,('P',5):.2,('P',10):.1,('R',10):1,('R',20):1}
            run_id=db.save_query(experiment,'unit','1','TF',result,metrics)
            for batch in range(180):
                db.save_timings([(run_id,batch*90+i,.1,.2,.3) for i in range(1,91)])
            reopened=Database(db.path)
            with reopened.connect() as con:
                self.assertEqual(con.execute('SELECT COUNT(*) FROM timing_samples').fetchone()[0],16200)
                self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_complete_experiment_persists_and_exports(self):
        docs=[{'doc_id':'1','title':'','body':'alpha beta','author':'','bib':''},{'doc_id':'2','title':'','body':'beta gamma','author':'','bib':''}]
        queries=[{'query_id':'1','source_query_id':'001','text':'alpha','split':'TEST'}]
        qrels=[{'query_id':'1','doc_id':'1','raw_grade':2}]
        manifest={'dataset_id':'unit','name':'unit','language':'en','source_url':'unit','files':{'unit':'hash'}}
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'unit.sqlite3');db.import_dataset(docs,queries,qrels,manifest)
            engine=RetrievalEngine(docs)
            result=run_experiment(engine,db,queries,qrels,manifest,repeats=2,bootstrap=20,results_root=Path(tmp)/'results',artifact_directory=Path(tmp)/'index')
            self.assertEqual(result['query_count'],1)
            self.assertEqual(db.history()[0]['status'],'COMPLETED')
            for m in ('BINARY','TF','TFIDF'):
                self.assertEqual(result['methods'][m]['MAP'],1)
                self.assertEqual(result['methods'][m]['timing']['samples'],2)
            target=Path(tmp)/'results'/result['experiment_id']
            self.assertTrue(all((target/name).is_file() for name in EXPORT_FILES))
            counts={row['table']:row['rows'] for row in db.overview()}
            self.assertEqual(counts['query_runs'],3);self.assertEqual(counts['query_metrics'],18);self.assertEqual(counts['timing_samples'],6)
            with db.connect() as con:
                self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(),[])
                with self.assertRaises(sqlite3.IntegrityError):
                    con.execute("INSERT INTO qrels VALUES('unit','999','1',1)")
                with self.assertRaises(sqlite3.IntegrityError):
                    con.execute("INSERT INTO ranked_results VALUES('nonexistent',1,'unit','1',0.5)")

if __name__ == '__main__':unittest.main()
