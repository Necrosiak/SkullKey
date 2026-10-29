import importlib.util
import os
from pathlib import Path
import tempfile
import unittest


class TouchupCheckpointTests(unittest.TestCase):
    def module(self):
        path=Path(__file__).resolve().parents[1]/'defaults/scripts/Extensions/EA/ea.py'
        spec=importlib.util.spec_from_file_location('checkpoint_fixture',path)
        ea=importlib.util.module_from_spec(spec);spec.loader.exec_module(ea)
        return ea

    def test_appending_other_output_cannot_reuse_old_completion(self):
        ea=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'__Installer';p.mkdir();log=p/'InstallLog.txt'
            log.write_bytes('Installer finished with exit code: 3\n'.encode('utf-16'))
            checkpoint=ea.touchup_checkpoint(tmp)
            with log.open('ab') as f:f.write('New installer started\n'.encode('utf-16-le'))
            self.assertIsNone(ea.touchup_exit(tmp,0,checkpoint))
            with log.open('ab') as f:f.write('Installer finished with exit code: 0\n'.encode('utf-16-le'))
            self.assertEqual(ea.touchup_exit(tmp,0,checkpoint),0)

    def test_replaced_log_is_read_from_its_new_start(self):
        ea=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'__Installer';p.mkdir();log=p/'InstallLog.txt'
            log.write_bytes(('old output\n'*40).encode('utf-16'))
            checkpoint=ea.touchup_checkpoint(tmp)
            replacement=p/'new';replacement.write_bytes('Installer finished with exit code: 9\n'.encode('utf-16'))
            replacement.replace(log)
            self.assertEqual(ea.touchup_exit(tmp,0,checkpoint),9)

    def test_old_completion_outside_bounded_tail_is_ignored(self):
        ea=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'__Installer';p.mkdir();log=p/'InstallLog.txt'
            log.write_bytes(b'Installer finished with exit code: 3\n'+b'x'*(5<<20))
            self.assertIsNone(ea.touchup_exit(tmp,0))

    def test_nonexistent_and_inaccessible_structure_is_harmless(self):
        ea=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'file';p.write_text('fixture')
            self.assertIsNone(ea.touchup_checkpoint(p))
            self.assertIsNone(ea.touchup_exit(p,0))
