"""Issue #10 diagnostic reproductions; fake CLI, temporary files, no EA account.

Some assertions deliberately document problematic current behavior, not fixes.
"""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch


@unittest.skipIf(os.name == 'nt', 'Linux worker and process groups')
class Issue10Tests(unittest.TestCase):
    def module(self):
        path = Path(__file__).resolve().parents[1] / 'defaults/scripts/Extensions/EA/ea.py'
        spec = importlib.util.spec_from_file_location('issue10_ea_fixture', path)
        ea = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ea)
        return ea

    def run_hanging_fixture(self, error=False, stale_cancel=False):
        ea = self.module()
        with tempfile.TemporaryDirectory(prefix='ea-issue10-') as tmp, \
                patch.dict(os.environ, {'SK_ACCOUNT_DIR': str(Path(tmp) / 'account')}):
            root = ea.root()
            auth = root / 'data/maxima/auth.toml'
            auth.parent.mkdir(parents=True)
            auth.write_text('fake fixture, no account')
            ea.save({'validated': True, 'games': [{'slug': 'fixture', 'installed': False}]})
            cli = root / 'fake-cli'
            cli.write_text('#!/usr/bin/env python3\nimport pathlib,sys,time\n'
                           'p=pathlib.Path(sys.argv[-1]); (p/"fixture.bin").write_bytes(b"fixture")\n'
                           'print("Progress: 100", flush=True)\n' +
                           ('print("ERROR fixture-finalization-failed", flush=True)\n' if error else '') +
                           'time.sleep(15)\n')
            cli.chmod(0o700)
            ea.write_job('fixture', {'token': 'current', 'active': True, 'Percentage': 0,
                                    'Description': 'Starting', 'Error': None})
            if stale_cancel:
                (root / 'cancel-fixture').write_text('older-attempt')
            with patch.object(ea, 'client', return_value=cli), \
                    patch.object(ea, 'env', return_value={'PATH': '/usr/bin:/bin'}):
                thread = threading.Thread(target=ea.install_worker, args=('fixture', 'current'), daemon=True)
                thread.start()
                try:
                    deadline = time.monotonic() + 4
                    while time.monotonic() < deadline:
                        job = ea.read_job('fixture')
                        if job.get('Percentage') == 99:
                            break
                        time.sleep(.02)
                    # Allow the ERROR line to be consumed in that scenario.
                    time.sleep(.1)
                    job = ea.read_job('fixture')
                    self.assertTrue(thread.is_alive())
                    self.assertTrue(job['active'])
                    self.assertEqual(job['Percentage'], 99)
                    self.assertIsNone(job['Error'])
                    self.assertEqual(job['Description'], 'Waiting for EA installation to finish…')
                    self.assertNotIn('fixture-finalization-failed', ea.job_path('fixture').read_text())
                    diagnostic = json.loads((root / 'install-diagnostic-fixture.json').read_text())
                    self.assertEqual(diagnostic['stage'], 'waiting-for-cli-exit')
                    self.assertEqual(diagnostic['cli_error_seen'], error)
                    self.assertNotIn('fixture-finalization-failed', json.dumps(diagnostic))
                finally:
                    (root / 'cancel-fixture').write_text('current')
                    thread.join(timeout=7)
                self.assertFalse(thread.is_alive())
                final = ea.read_job('fixture')
                self.assertFalse(final['active'])
                self.assertEqual(final['Description'], 'Cancelled — downloaded files kept')
                self.assertTrue((ea.game_dir('fixture') / 'fixture.bin').exists())

    def test_live_cli_at_100_percent_is_shown_as_99_until_exit(self):
        self.run_hanging_fixture()

    def test_error_then_hanging_cli_still_shows_99_and_null_error(self):
        self.run_hanging_fixture(error=True)

    def test_old_cancel_marker_does_not_cancel_new_job(self):
        self.run_hanging_fixture(stale_cancel=True)

    def test_zero_byte_file_cannot_pass_installation_verification(self):
        ea = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'empty.exe').touch()
            self.assertFalse(ea.installation_verified('fixture', directory,
                '{"slug":"fixture","installed":true}'))

    def test_timeout_is_controlled_and_preserves_game_files(self):
        ea = self.module()
        with tempfile.TemporaryDirectory(prefix='ea-issue10-timeout-') as tmp, \
                patch.dict(os.environ, {'SK_ACCOUNT_DIR': str(Path(tmp) / 'account')}):
            root = ea.root()
            auth = root / 'data/maxima/auth.toml'
            auth.parent.mkdir(parents=True)
            auth.write_text('fake fixture')
            ea.save({'validated': True, 'games': [{'slug': 'fixture', 'installed': False}]})
            game = ea.game_dir('fixture'); game.mkdir(parents=True)
            (game / 'keep.bin').write_bytes(b'fixture')
            cli = root / 'fake-cli'
            cli.write_text('#!/usr/bin/env python3\nimport time\ntime.sleep(15)\n')
            cli.chmod(0o700)
            ea.write_job('fixture', {'token': 'current', 'active': True, 'Percentage': 99, 'Error': None})
            ticks = iter([0, 43201])
            with patch.object(ea, 'client', return_value=cli), \
                    patch.object(ea, 'env', return_value={'PATH': '/usr/bin:/bin'}), \
                    patch.object(ea, 'time', types.SimpleNamespace(monotonic=lambda: next(ticks), time=time.time)):
                ea.install_worker('fixture', 'current')
            job = ea.read_job('fixture')
            self.assertFalse(job['active'])
            self.assertIsNotNone(job['Error'])
            self.assertTrue((game / 'keep.bin').exists())

    def test_install_diagnostic_drops_non_allowlisted_secret_fields(self):
        ea = self.module()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SK_ACCOUNT_DIR': tmp}):
            ea.install_diagnostic('fixture', 'cli-running', time.time(), progress=99,
                                  token='fixture-secret', raw_output='fixture-secret',
                                  url='https://fixture.invalid/?code=fixture-secret')
            data = json.loads((ea.root() / 'install-diagnostic-fixture.json').read_text())
            self.assertNotIn('fixture-secret', json.dumps(data))
            self.assertEqual(data['progress'], 99)


if __name__ == '__main__':
    unittest.main(verbosity=2)
