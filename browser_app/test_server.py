import io
from pathlib import Path
import tempfile
import time
import unittest
from browser_app.server import create_app


class BrowserTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.app=create_app(Path(self.directory.name))
        self.app.config['TESTING']=True
        self.client=self.app.test_client()
        self.client.get('/')
        with self.client.session_transaction() as session:self.headers={'X-GEMX-Token':session['csrf']}

    def tearDown(self):
        self.app.extensions['jobs'].close()
        self.directory.cleanup()

    def test_demo_runs_real_exports_and_mujoco_validation(self):
        response=self.client.post('/api/jobs/demo',json={'neutral_seconds':.5},headers=self.headers)
        self.assertEqual(response.status_code,202)
        key=response.json['id'];deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            status=self.client.get('/api/jobs/'+key).json
            if status['status'] in ('completed','failed'):break
            time.sleep(.05)
        self.assertEqual(status['status'],'completed',status)
        data=self.client.get('/api/jobs/'+key+'/data').json
        self.assertEqual(len(data['positions']),60)
        self.assertEqual(data['validation']['status'],'passed')
        self.assertEqual(data['validation']['joints'],77)
        self.assertIn(None,data['angles']['left']['axial'])
        for name in ('csv','report','zip'):
            response=self.client.get(f'/api/jobs/{key}/files/{name}')
            self.assertEqual(response.status_code,200)
            self.assertTrue(response.data)
            response.close()
        self.assertEqual(self.client.get(f'/api/jobs/{key}/files/request.json').status_code,404)

    def test_mutations_require_page_token(self):
        self.assertEqual(self.client.post('/api/jobs/demo',json={}).status_code,403)
        self.assertEqual(self.client.post('/api/jobs/demo',json={},headers={**self.headers,'Origin':'https://unrelated.example'}).status_code,403)

    def test_invalid_neutral_period_creates_no_job(self):
        for value in (-1,2,99,'not-a-number'):
            response=self.client.post('/api/jobs/demo',json={'neutral_seconds':value},headers=self.headers)
            self.assertEqual(response.status_code,400)
        self.assertEqual(self.app.extensions['jobs'].items,{})

    def test_unconfigured_video_does_not_accept_upload(self):
        response=self.client.post('/api/jobs/video',data={'video':(io.BytesIO(b'not video'),'test.mp4')},headers=self.headers)
        self.assertEqual(response.status_code,503)
        self.assertEqual(self.app.extensions['jobs'].items,{})

    def test_unknown_job_and_untrusted_host(self):
        self.assertEqual(self.client.get('/api/jobs/not-a-job').status_code,404)
        self.assertEqual(self.client.get('/',headers={'Host':'unrelated.example'}).status_code,400)


if __name__=='__main__':unittest.main()
