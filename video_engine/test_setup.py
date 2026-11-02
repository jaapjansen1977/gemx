import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from .models import download,make_config
from .paths import load_profile


class Response(io.BytesIO):
    def __init__(self,data,status=200,headers=None):super().__init__(data);self.status=status;self.headers=headers or {}


class SetupTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def test_resumed_download_is_hash_verified(self):
        target=self.root/'weights.bin';target.with_suffix('.bin.part').write_bytes(b'abc')
        def opener(req,timeout):
            self.assertEqual(req.get_header('Range'),'bytes=3-')
            return Response(b'def',206,{'Content-Range':'bytes 3-5/6'})
        download('https://official.example/weights',target,hashlib.sha256(b'abcdef').hexdigest(),6,opener)
        self.assertEqual(target.read_bytes(),b'abcdef')

    def test_server_without_range_support_restarts_safely(self):
        target=self.root/'weights.bin';target.with_suffix('.bin.part').write_bytes(b'old')
        download('https://official.example/weights',target,hashlib.sha256(b'abcdef').hexdigest(),6,lambda *a,**kw:Response(b'abcdef'))
        self.assertEqual(target.read_bytes(),b'abcdef')

    def test_corrupt_download_never_becomes_verified_model(self):
        target=self.root/'weights.bin'
        with self.assertRaisesRegex(ValueError,'SHA256'):
            download('https://official.example/weights',target,hashlib.sha256(b'good').hexdigest(),4,lambda *a,**kw:Response(b'evil'))
        self.assertFalse(target.exists());self.assertFalse(target.with_suffix('.bin.part').exists())

    def test_existing_wrong_file_is_preserved(self):
        target=self.root/'weights.bin';target.write_bytes(b'user')
        with self.assertRaises(ValueError):download('https://official.example/weights',target,hashlib.sha256(b'good').hexdigest(),4)
        self.assertEqual(target.read_bytes(),b'user')

    def test_config_changes_paths_only_and_preserves_original(self):
        import yaml
        config={'pose':{'checkpoint':'../../weights/body_s240000.ckpt','batch_size':4},'observations':{'checkpoint':'../../weights/vitpose.pth'},'detector':{'checkpoint':'../../weights/yolox_humanart.onnx'},'motion':{'checkpoint':'../../weights/motion_native77_e774_s292175.ckpt','stats':'../../weights/motion_stats_raw.npz','network':{'max_len':120}}}
        original=yaml.safe_dump(config);(self.root/'body_video_native77.yaml').write_text(original)
        result=yaml.safe_load(make_config(self.root).read_text())
        self.assertEqual((self.root/'body_video_native77.yaml').read_text(),original)
        self.assertEqual(result['motion']['network'],config['motion']['network'])
        self.assertEqual(result['pose']['checkpoint'],str(self.root/'body_s240000.ckpt'))

    def test_only_verified_complete_profile_is_auto_loaded(self):
        with patch.dict(os.environ,{'LOCALAPPDATA':str(self.root)}):
            path=self.root/'GEMX/engine.json';path.parent.mkdir()
            python=self.root/'python.exe';python.touch();config=self.root/'runtime.yaml';config.touch();assets=self.root/'soma';assets.mkdir()
            value=dict(status='incomplete',python=str(python),config=str(config),assets=str(assets))
            path.write_text(json.dumps(value));self.assertIsNone(load_profile())
            value['status']='ready_for_video_test';path.write_text(json.dumps(value));self.assertEqual(load_profile()['python'],str(python))
            config.unlink();self.assertIsNone(load_profile())


if __name__=='__main__':unittest.main()
