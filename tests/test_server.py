import json
import tempfile
import threading
from pathlib import Path
import unittest
import urllib.error
import urllib.request
from ir_system.service import Service
from ir_system.server import make_server

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.service=Service(Path(cls.tmp.name)/'test.sqlite3')
        cls.server=make_server(cls.service,port=0)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()

    def test_status_and_static_ui(self):
        with urllib.request.urlopen(self.url+'/api/status') as response:
            self.assertEqual(json.load(response)['dataset']['counts']['documents'],1400)
        with urllib.request.urlopen(self.url+'/') as response:
            self.assertIn('IR Lab',response.read().decode())

    def test_search_api_returns_three_methods(self):
        request=urllib.request.Request(self.url+'/api/search',data=json.dumps({'query_id':'3','top_k':2}).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request) as response:result=json.load(response)
        self.assertEqual(set(result['methods']),{'BINARY','TF','TFIDF'})
        self.assertEqual(result['query']['source_query_id'],'004')
        self.assertTrue(all(len(m['items'])<=2 for m in result['methods'].values()))

    def test_invalid_topk_is_rejected(self):
        request=urllib.request.Request(self.url+'/api/search',data=b'{"query":"alpha","top_k":500}',headers={'Content-Type':'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as cm:urllib.request.urlopen(request)
        self.assertEqual(cm.exception.code,400)

    def test_path_traversal_not_served(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:urllib.request.urlopen(self.url+'/../schema.sql')
        self.assertEqual(cm.exception.code,404)

    def test_cross_origin_mutation_rejected(self):
        request=urllib.request.Request(self.url+'/api/search',data=b'{}',headers={'Content-Type':'application/json','Origin':'https://example.invalid'})
        with self.assertRaises(urllib.error.HTTPError) as cm:urllib.request.urlopen(request)
        self.assertEqual(cm.exception.code,403)

if __name__ == '__main__':unittest.main()
