import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from .export_results import export
from .fit import load_model

ROOT=Path(__file__).resolve().parents[1]


class ModelExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.target=Path(cls.temp.name)/'export'
        cls.report=export(ROOT/'myo_fit/results/fit.npz',cls.target,ROOT/'myo_fit/results/report.json')

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_values_are_exact_model_qpos(self):
        with np.load(ROOT/'myo_fit/results/fit.npz',allow_pickle=False) as saved, np.load(self.target/'model-coordinates.npz',allow_pickle=False) as result:
            np.testing.assert_array_equal(result['qpos'],saved['qpos'])
            for index,coordinate in enumerate(self.report['coordinates']):
                expected=saved['qpos'][:,coordinate['qpos_address']]
                if coordinate['unit']=='deg':expected=np.rad2deg(expected)
                np.testing.assert_array_equal(result['values'][:,index],expected)
        with (self.target/'angles.csv').open(newline='') as stream:
            rows=list(csv.reader(stream))
        self.assertEqual(len(rows),61);self.assertEqual(len(rows[0]),124)
        self.assertFalse(self.report['zero_correction_applied'])
        self.assertEqual(self.report['source'],'mujoco_myofullbody_fit')

    def test_roles_and_replay_match_saved_model(self):
        counts={role:sum(c['role']==role for c in self.report['coordinates']) for role in ('optimized','coupled','fixed_reference')}
        self.assertEqual(counts,dict(optimized=31,coupled=51,fixed_reference=40))
        # Native MuJoCo arithmetic can round differently on Windows and Linux.
        # Keep this stricter than the exporter's 1e-8 m rejection threshold.
        self.assertLessEqual(self.report['validation']['max_saved_body_position_error_m'],1e-12)
        self.assertEqual(self.report['fit_sha256'],hashlib.sha256((ROOT/'myo_fit/results/fit.npz').read_bytes()).hexdigest())

    def test_corrupt_fit_is_not_exported_as_valid(self):
        with np.load(ROOT/'myo_fit/results/fit.npz',allow_pickle=False) as saved:
            arrays={k:saved[k].copy() for k in saved.files}
        arrays['qpos'][0,0]+=.1
        path=Path(self.temp.name)/'corrupt.npz';np.savez_compressed(path,**arrays)
        with self.assertRaisesRegex(ValueError,'does not reproduce'):
            export(path,Path(self.temp.name)/'corrupt-output',ROOT/'myo_fit/results/report.json')

    def test_replay_accepts_sub_picometer_platform_roundoff(self):
        with np.load(ROOT/'myo_fit/results/fit.npz',allow_pickle=False) as saved:
            arrays={k:saved[k].copy() for k in saved.files}
        arrays['body_positions_m'][0,0,0]+=1e-15
        path=Path(self.temp.name)/'roundoff.npz';np.savez_compressed(path,**arrays)
        report=export(path,Path(self.temp.name)/'roundoff-output',ROOT/'myo_fit/results/report.json')
        error=report['validation']['max_saved_body_position_error_m']
        self.assertGreater(error,0.)
        self.assertLessEqual(error,1e-12)


if __name__=='__main__':unittest.main()
