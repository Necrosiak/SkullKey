import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class InstallerWarningTests(unittest.TestCase):
    def module(self):
        path=Path(__file__).resolve().parents[1]/'defaults/scripts/Extensions/EA/ea.py'
        spec=importlib.util.spec_from_file_location('ea_warning_fixture',path)
        ea=importlib.util.module_from_spec(spec);spec.loader.exec_module(ea)
        return ea

    def test_verified_legacy_diagnostic_is_exposed_without_reinstalling(self):
        ea=self.module()
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'SK_ACCOUNT_DIR':tmp}), \
                patch.object(ea,'description',return_value='Fixture'),patch.object(ea,'cover',return_value=None):
            ea.save({'games':[{'slug':'fixture','name':'Fixture','installed':True}]})
            (ea.root()/'install-diagnostic-fixture.json').write_text(json.dumps({'stage':'done','touchup_exit':3}))
            self.assertEqual(ea.installer_exit_code('fixture'),3)
            self.assertEqual(ea.dispatch('getgamedetails',['fixture'])['Content']['InstallerExitCode'],3)

    def test_failed_attempt_does_not_become_installed_warning(self):
        ea=self.module()
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'SK_ACCOUNT_DIR':tmp}):
            ea.save({'games':[{'slug':'fixture','installed':True}]})
            (ea.root()/'install-diagnostic-fixture.json').write_text(json.dumps({'stage':'failed','touchup_exit':3}))
            self.assertIsNone(ea.installer_exit_code('fixture'))

    def test_uninstalled_game_and_invalid_codes_are_not_warned(self):
        ea=self.module()
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'SK_ACCOUNT_DIR':tmp}):
            for installed,code in [(False,3),(True,True),(True,'3'),(True,0)]:
                ea.save({'games':[{'slug':'fixture','installed':installed}], 'installer_warnings':{'fixture':code}})
                self.assertIsNone(ea.installer_exit_code('fixture'))
