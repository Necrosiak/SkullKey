"""Actual worker + synthetic CLI: no account, network, Wine or game download."""
import importlib.util
import itertools
import json
import os
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import patch


class WorkerWatchdogTests(unittest.TestCase):
    def run_fixture(self, verified=True, waiting=False, touchup_code=3):
        path = Path(__file__).resolve().parents[1] / 'defaults/scripts/Extensions/EA/ea.py'
        spec = importlib.util.spec_from_file_location('ea_worker_fixture', path)
        ea = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ea)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SK_ACCOUNT_DIR': tmp}):
            root = ea.root()
            auth = root / 'data/maxima/auth.toml'
            auth.parent.mkdir(parents=True)
            auth.write_text('synthetic fixture only')
            queue = root / 'data/maxima/download_queue.json'
            queue.write_text('{"current":"old-cancelled-game"}')
            ea.save({'validated': True, 'games': [{'slug': 'fixture', 'installed': False}], 'installer_warnings': {'fixture': 7}})
            cli = root / 'fixture-cli'
            cli.write_text('#!/usr/bin/env python3\nimport pathlib,sys,time\n'
                'if sys.argv[1] == "install":\n'
                ' p=pathlib.Path(sys.argv[-1]); (p/"game.exe").write_bytes(b"fixture")\n'
                ' d=p/"__Installer"; d.mkdir()\n'
                ' (d/"InstallLog.txt").write_bytes("Installer finished with exit code: ' + str(touchup_code) + '\\n".encode("utf-16"))\n'
                ' print("Progress: ' + ('100' if waiting else '99.99') + '",flush=True)\n' +
                (' print("ERROR fixture failure",flush=True); time.sleep(.5); sys.exit(3)\n' if waiting else
                 ' while True: time.sleep(.1)\n') +
                'else: print(\'{"slug":"fixture","installed":' + ('true' if verified else 'false') + '}\')\n')
            cli.chmod(0o700)
            ea.write_job('fixture', {'token':'test', 'active':True, 'Percentage':0, 'Error':None})
            ticks = itertools.count(1000, 20)
            def refresh():
                state = ea.state(); state['games'][0]['installed'] = True; ea.save(state)
            with patch.object(ea, 'client', return_value=cli), \
                 patch.object(ea, 'localized_client', return_value=cli), \
                 patch.object(ea, 'env', return_value={'PATH':'/usr/bin:/bin'}), \
                 patch.object(ea, 'refresh', side_effect=refresh) as refreshed, \
                 patch.object(ea, 'prefix_processes', return_value=[]), \
                 patch.object(ea, 'apply_locale_filter'), \
                 patch.object(ea, 'time', types.SimpleNamespace(time=time.time, monotonic=lambda:next(ticks))):
                if waiting:
                    with patch.object(ea.InstallWatchdog, 'check',
                         lambda dog,*a,**kw: setattr(dog,'action','installer-waiting')):
                        ea.install_worker('fixture','test')
                else:
                    ea.install_worker('fixture','test')
            result = ea.read_job('fixture')
            diagnostic = json.loads((root/'install-diagnostic-fixture.json').read_text())
            self.assertFalse(queue.exists(), 'old Maxima queue removed before install')
            self.assertTrue((ea.game_dir('fixture')/'game.exe').exists())
            self.assertFalse(result['active'])
            self.assertNotIn('synthetic fixture', json.dumps(diagnostic))
            if verified and not waiting:
                exposed = ea.dispatch('getprogress', ['fixture'])['Content']
                if touchup_code:
                    self.assertEqual(result.get('InstallerExitCode'),touchup_code)
                    self.assertEqual(exposed.get('InstallerExitCode'),touchup_code)
                    self.assertEqual(ea.state()['installer_warnings'].get('fixture'),touchup_code)
                else:
                    self.assertNotIn('InstallerExitCode',result)
                    self.assertNotIn('InstallerExitCode',exposed)
                    self.assertNotIn('fixture',ea.state()['installer_warnings'])
            return result, diagnostic, refreshed.call_count

    def test_9999_stops_empty_prefix_after_touchup_and_preserves_final_evidence(self):
        job, diag, calls = self.run_fixture()
        self.assertEqual(job['Percentage'],100)
        self.assertEqual(diag['stage'],'done')
        self.assertEqual(diag['watchdog'],'stopped-maxima')
        self.assertEqual(diag['touchup_exit'],3)
        self.assertEqual(diag['max_progress'],99.99)
        self.assertEqual(calls,1)

    def test_watchdog_does_not_bypass_installation_verification(self):
        job, diag, calls = self.run_fixture(verified=False)
        self.assertIsNotNone(job['Error'])
        self.assertEqual(diag['stage'],'failed')
        self.assertEqual(diag['watchdog'],'stopped-maxima')
        self.assertEqual(diag['touchup_exit'],3)
        self.assertEqual(calls,0)

    def test_successful_touchup_clears_previous_installer_warning(self):
        job, diag, calls = self.run_fixture(touchup_code=0)
        self.assertEqual(job['Percentage'],100)
        self.assertEqual(diag['touchup_exit'],0)
        self.assertEqual(calls,1)

    def test_waiting_message_does_not_mask_cli_error(self):
        job, diag, calls = self.run_fixture(waiting=True)
        self.assertIsNotNone(job['Error'])
        self.assertEqual(diag['stage'],'failed')
        self.assertEqual(diag['watchdog'],'installer-waiting')
        self.assertEqual(calls,0)


if __name__ == '__main__':
    unittest.main()
