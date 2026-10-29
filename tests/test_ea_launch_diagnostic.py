import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch


class LaunchDiagnosticTests(unittest.TestCase):
    def module(self):
        path=Path(__file__).resolve().parents[1]/'defaults/scripts/Extensions/EA/ea.py'
        spec=importlib.util.spec_from_file_location('ea_launch_test',path)
        ea=importlib.util.module_from_spec(spec);spec.loader.exec_module(ea)
        return ea

    def test_classifies_opengl_without_persisting_output_or_key(self):
        ea=self.module()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'SK_ACCOUNT_DIR':tmp}):
            result=types.SimpleNamespace(returncode=1,stdout='GLW_StartOpenGL: could not load OpenGL subsystem',
                stderr='cdkey=private-fixture-token https://example.invalid/?token=private-fixture-token')
            ea.launch_diagnostic('fixture',ea.time.monotonic(),result)
            text=(ea.root()/'launch-diagnostic-fixture.json').read_text();data=json.loads(text)
            self.assertEqual(data['categories'],['opengl'])
            self.assertEqual(data['exit_code'],1)
            self.assertNotIn('private-fixture',text)
            self.assertNotIn('https:',text)

    def test_success_without_error_marker_is_not_reported_as_crash(self):
        ea=self.module()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'SK_ACCOUNT_DIR':tmp}):
            ea.launch_diagnostic('fixture',ea.time.monotonic(),types.SimpleNamespace(returncode=0,stdout='',stderr=''))
            data=json.loads((ea.root()/'launch-diagnostic-fixture.json').read_text())
            self.assertEqual(data['categories'],[])
            self.assertEqual(data['exit_code'],0)

    def test_write_failure_does_not_break_launch(self):
        ea=self.module()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'SK_ACCOUNT_DIR':tmp}), \
                patch.object(ea.tempfile,'NamedTemporaryFile',side_effect=OSError('fixture')):
            ea.launch_diagnostic('fixture',ea.time.monotonic(),types.SimpleNamespace(returncode=1,stdout='',stderr=''))

    def test_mesa_workaround_is_scoped_to_moh(self):
        ea=self.module()
        with patch.object(ea,'env',side_effect=lambda:{'FIXTURE':'value'}):
            self.assertEqual(ea.launch_environment('medal-of-honor-allied-assault')['MESA_EXTENSION_MAX_YEAR'],'2002')
            self.assertNotIn('MESA_EXTENSION_MAX_YEAR',ea.launch_environment('battlefield-1942'))

    def test_existing_explicit_mesa_setting_is_preserved(self):
        ea=self.module()
        with patch.object(ea,'env',side_effect=lambda:{'MESA_EXTENSION_MAX_YEAR':'2001'}):
            self.assertEqual(ea.launch_environment('medal-of-honor-allied-assault')['MESA_EXTENSION_MAX_YEAR'],'2001')
