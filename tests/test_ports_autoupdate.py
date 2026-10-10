"""Regression checks for releases, cached links and user files during updates."""
import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

scripts = Path(__file__).resolve().parents[1] / "defaults/scripts"
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location("ports_autoupdate_test", scripts / "ports.py")
ports = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ports)

class AutoUpdateTests(unittest.TestCase):
    def test_all_catalog_patterns_compile(self):
        import re
        for port in ports.PORTS:
            with self.subTest(port=port["shortname"]):
                re.compile(port["asset"])
                self.assertNotIn(r"\\", port["asset"])

    def test_missing_stable_asset_falls_back_to_compatible_release(self):
        port = ports.APPS["pt-pc"]
        release = {"tag_name":"v2", "assets":[{"name":"P.T.PC.Port.Setup-linux", "updated_at":"2026-10-11T12:00:00Z", "browser_download_url":"https://example.com/new", "size":2}]}
        with patch.object(ports, "http_json", side_effect=[{"assets":[{"name":"windows.zip"}]}, [release]]):
            info = ports.release_info({"releases":{}}, port)
        self.assertEqual(info["url"], "https://example.com/new")

    def test_same_day_rolling_asset_is_detected(self):
        port = ports.APPS["pt-pc"]
        def release(hour):
            return {"tag_name":"rolling", "assets":[{"name":"P.T.PC.Port.Setup-linux", "updated_at":f"2026-10-11T{hour}:00:00Z", "browser_download_url":"https://example.com/new", "size":2}]}
        with patch.object(ports, "http_json", side_effect=[release("10"),release("11")]):
            first = ports.release_info({"releases":{}}, port)
            second = ports.release_info({"releases":{}}, port)
        self.assertNotEqual(first["tag"], second["tag"])

    def test_fresh_release_is_passed_to_worker_and_only_installed_ports_updated(self):
        state = {"apps":{"pt-pc":{"installed":True,"tag":"old","steamClientID":"42"}, "acgc-pc-port":{"installed":False}},"releases":{}}
        fresh = {"tag":"new@2026-10-11T11:00:00Z","url":"https://example.com/new"}
        with patch.object(ports,"load_state",side_effect=lambda:copy.deepcopy(state)), patch.object(ports,"save_state"), patch.object(ports,"release_info",return_value=fresh) as lookup, patch.object(ports,"worker_install",return_value=True) as install, patch.object(ports,"_update_event") as notify:
            ports.worker_autoupdate()
        lookup.assert_called_once()
        install.assert_called_once_with("pt-pc",release=fresh)
        self.assertTrue(notify.call_args.args[3])

    def test_failed_install_is_not_reported_as_success(self):
        state = {"apps":{"pt-pc":{"installed":True,"tag":"old"}},"releases":{}}
        with patch.object(ports,"load_state",side_effect=lambda:copy.deepcopy(state)), patch.object(ports,"save_state"), patch.object(ports,"release_info",return_value={"tag":"new"}), patch.object(ports,"worker_install",return_value=False), patch.object(ports,"_update_event") as notify:
            ports.worker_autoupdate()
        self.assertFalse(notify.call_args.args[3])

    def test_legacy_stamp_migrates_without_reinstall(self):
        state = {"apps":{"pt-pc":{"installed":True,"tag":"v1@2026-10-11"}},"releases":{}}
        with patch.object(ports,"load_state",return_value=state), patch.object(ports,"save_state"), patch.object(ports,"release_info",return_value={"tag":"v1@2026-10-11T10:00:00Z"}), patch.object(ports,"worker_install") as install, patch.object(ports,"_update_event") as notice:
            ports.worker_autoupdate()
        install.assert_not_called()
        notice.assert_not_called()
        self.assertEqual(state["apps"]["pt-pc"]["tag"],"v1@2026-10-11T10:00:00Z")

    def test_lookup_failure_does_not_stop_other_ports(self):
        state = {"apps":{"pt-pc":{"installed":True,"tag":"old"},"acgc-pc-port":{"installed":True,"tag":"new"}},"releases":{}}
        with patch.object(ports,"load_state",return_value=state), patch.object(ports,"save_state"), patch.object(ports,"release_info",side_effect=[RuntimeError("unavailable"),{"tag":"new"}]) as lookup, patch.object(ports,"worker_install") as install:
            ports.worker_autoupdate()
        self.assertEqual(lookup.call_count,2)
        install.assert_not_called()

    def test_existing_settings_rom_and_save_survive_archive_update(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            target=root/"game"
            target.mkdir()
            existing={"settings.ini":"custom", "save/town.gci":"my town", "rom/disc.iso":"my disc", "AnimalCrossing.exe":"old"}
            for name,value in existing.items():
                path=target/name
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(value)
            archive=root/"release.zip"
            with zipfile.ZipFile(archive,"w") as output:
                for name in existing:
                    output.writestr(name,"new")
            with patch.object(ports,"RUNTIME_DIR",root), patch.object(ports,"write_progress"):
                ports._install_archive(archive,target,"acgc-pc-port","Animal Crossing",updating=True)
            for name,value in existing.items():
                self.assertEqual((target/name).read_text(),"new" if name.endswith(".exe") else value)

    def test_pt_update_without_source_package_uses_imported_archives(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            game=root/"pt-pc"
            (game/"CUSA01127").mkdir(parents=True)
            for name in ("chunk1.psarc","texture.qar"):
                (game/"CUSA01127"/name).write_bytes(b"original")
            port={**ports.APPS["pt-pc"],"pkg_source":str(root/"absent.pkg")}
            def download(url,destination,*args):
                destination.parent.mkdir(parents=True,exist_ok=True)
                destination.write_bytes(b"setup")
            def run(command,**kwargs):
                self.assertEqual(command[2],"")
                Path(command[4]).write_text("PASS updated")
                return SimpleNamespace(returncode=0,stdout="",stderr="")
            with patch.object(ports,"RUNTIME_DIR",root),patch.object(ports,"download_file",side_effect=download),patch.object(ports,"write_progress"),patch.object(ports.subprocess,"run",side_effect=run):
                ports._install_pt_setup(port,{"url":"https://example.com/setup","name":"setup","tag":"new"},game,"pt-pc")
            self.assertEqual((game/"CUSA01127/chunk1.psarc").read_bytes(),b"original")

if __name__ == "__main__":
    unittest.main()
