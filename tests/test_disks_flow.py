"""Discs & Installers: add → install → finalize → setexe → cancel flow."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "defaults" / "scripts"
STUB = r"""#!/usr/bin/env python3
import os, sys
a = sys.argv[1:]
if a[0] == "l":
    print("Size = 10"); sys.exit(0)
out = next(x[2:] for x in a if x.startswith("-o"))
os.makedirs(out, exist_ok=True)
open(os.path.join(out, "setup.exe"), "w").write("MZ")
print("100%")
"""


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.runtime, self.home, self.compat = t / "runtime", t / "home", t / "compat"
        for p in (self.runtime, self.home, self.compat, t / "bin"):
            p.mkdir()
        stub = t / "bin" / "7z"
        stub.write_text(STUB)
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        self.env = {**os.environ, "DECKY_PLUGIN_RUNTIME_DIR": str(self.runtime), "HOME": str(self.home),
                    "PATH": str(t / "bin") + os.pathsep + os.environ["PATH"],
                    "SK_DISKS_COMPAT_ROOT": str(self.compat), "SK_INSTALL_ROOT": ""}

    def tearDown(self):
        self.tmp.cleanup()

    def run_disks(self, *args):
        out = subprocess.run([sys.executable, str(SCRIPTS / "disks.py"), *args],
                             capture_output=True, text=True, env=self.env, timeout=60)
        lines = out.stdout.strip().splitlines()
        self.assertTrue(lines, out.stderr)
        return json.loads(lines[-1])

    def wait_stage(self, slug, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            state = json.loads((self.runtime / "disks" / "state.json").read_text())
            g = state["games"].get(slug, {})
            if g.get("stage") not in (None, "preparing"):
                return g
            time.sleep(0.1)
        self.fail("worker did not finish")

    def add(self, kind, path, title, parts=None):
        res = self.run_disks("add", json.dumps({"kind": kind, "path": str(path), "title": title,
                                                "parts": [str(p) for p in (parts or [path])]}))
        self.assertEqual(res["Type"], "Progress", res)
        return res["Content"]["ShortName"]

    def test_add_folder_copies_and_ranks(self):
        src = Path(self.tmp.name) / "My Games" / "Été Game"
        src.mkdir(parents=True)
        (src / "Game.exe").write_bytes(b"MZ")
        (src / "unins000.exe").write_bytes(b"MZ")
        slug = self.add("folder", src, "Été Game")
        g = self.wait_stage(slug)
        self.assertEqual(g["stage"], "ready")
        self.assertTrue(Path(g["root"], "game", "Game.exe").exists())
        cands = self.run_disks("finalize", slug)["Content"]["candidates"]
        self.assertEqual([Path(c["path"]).name for c in cands], ["Game.exe"])

    def test_add_image_needs_installer(self):
        iso = Path(self.tmp.name) / "game.iso"
        iso.write_bytes(b"x")
        slug = self.add("image", iso, "Game")
        g = self.wait_stage(slug)
        self.assertEqual(g["stage"], "needs-installer")
        self.assertEqual(Path(g["installer"]).name, "setup.exe")

    def test_install_returns_installer_launch_options(self):
        inst = Path(self.tmp.name) / "My Setups" / "setup_game_1.0.exe"
        inst.parent.mkdir()
        inst.write_bytes(b"MZ")
        slug = self.add("installer", inst, "Game")
        self.wait_stage(slug)
        res = self.run_disks("install", slug, "123")
        self.assertEqual(res["Type"], "LaunchOptions")
        self.assertEqual(res["Content"]["Exe"], f'"{inst}"')
        self.assertTrue(res["Content"]["Compatibility"])
        self.assertEqual(res["Content"]["WorkingDir"], str(inst.parent))

    def test_finalize_uses_prefix_diff(self):
        inst = Path(self.tmp.name) / "setup.exe"
        inst.write_bytes(b"MZ")
        drive_c = self.compat / "321" / "pfx" / "drive_c"
        (drive_c / "windows").mkdir(parents=True)
        (drive_c / "windows" / "old.exe").write_bytes(b"MZ")
        slug = self.add("installer", inst, "Foo")
        self.wait_stage(slug)
        self.run_disks("install", slug, "321")
        (drive_c / "Games" / "Foo").mkdir(parents=True)
        (drive_c / "Games" / "Foo" / "Foo.exe").write_bytes(b"MZ")
        cands = self.run_disks("finalize", slug)["Content"]["candidates"]
        self.assertEqual([Path(c["path"]).name for c in cands], ["Foo.exe"])
        res = self.run_disks("setexe", slug, cands[0]["path"])
        self.assertEqual(res["Type"], "Success")
        launch = self.run_disks("install", slug, "321")
        self.assertEqual(launch["Content"]["Exe"], f'"{cands[0]["path"]}"')

    def test_ready_folder_never_runs_its_setup(self):
        src = Path(self.tmp.name) / "Portable"
        src.mkdir()
        (src / "Game.exe").write_bytes(b"MZ")
        (src / "setup.exe").write_bytes(b"MZ")
        slug = self.add("ready", src, "Portable")
        g = self.wait_stage(slug)
        self.assertEqual((g["stage"], g["installer"]), ("ready", ""))

    def test_image_extract_removed_after_setexe(self):
        iso = Path(self.tmp.name) / "game.iso"
        iso.write_bytes(b"x")
        slug = self.add("image", iso, "Game")
        g = self.wait_stage(slug)
        self.assertTrue(Path(g["root"], "_extract").is_dir())
        exe = Path(g["root"], "_extract", "disc1", "setup.exe")
        self.run_disks("setexe", slug, str(Path(self.tmp.name) / "game.iso"))
        self.assertFalse(Path(g["root"], "_extract").exists())

    def test_image_without_installer_drops_extract(self):
        stub = Path(self.tmp.name) / "bin" / "7z"
        stub.write_text(stub.read_text().replace('"setup.exe"', '"Game.exe"'))
        iso = Path(self.tmp.name) / "plain.iso"
        iso.write_bytes(b"x")
        slug = self.add("image", iso, "Plain")
        g = self.wait_stage(slug)
        self.assertEqual(g["stage"], "ready")
        self.assertTrue(Path(g["root"], "game", "Game.exe").exists())
        self.assertFalse(Path(g["root"], "_extract").exists())

    def test_source_already_at_destination_is_never_deleted(self):
        src = self.home / "Games" / "Disques" / "foo"
        src.mkdir(parents=True)
        (src / "Foo.exe").write_bytes(b"MZ")
        slug = self.add("ready", src, "Foo")
        self.assertEqual(slug, "foo-2")
        self.wait_stage(slug)
        self.run_disks("cancelinstall", slug)
        self.assertTrue((src / "Foo.exe").exists())

    def test_source_containing_destination_is_refused(self):
        src = self.home / "Games"
        src.mkdir(parents=True, exist_ok=True)
        (src / "Some.exe").write_bytes(b"MZ")
        res = self.run_disks("add", json.dumps({"kind": "ready", "path": str(src), "title": "Games"}))
        self.assertEqual(res["Type"], "Error")

    def test_existing_folder_on_disk_gets_new_slug(self):
        (self.home / "Games" / "Disques" / "bar").mkdir(parents=True)
        src = Path(self.tmp.name) / "BarSrc"
        src.mkdir()
        (src / "Bar.exe").write_bytes(b"MZ")
        self.assertEqual(self.add("ready", src, "Bar"), "bar-2")

    def test_cancel_never_kills_an_unrelated_process(self):
        sleeper = subprocess.Popen(["sleep", "30"], start_new_session=True)
        try:
            src = Path(self.tmp.name) / "R2"
            src.mkdir()
            (src / "a.exe").write_bytes(b"MZ")
            slug = self.add("ready", src, "R2")
            self.wait_stage(slug)
            prog = self.runtime / "disks" / "progress" / f"{slug}.json"
            data = json.loads(prog.read_text())
            self.assertIsNone(data.get("pid"))          # finished worker leaves no pid
            data["pid"] = sleeper.pid                    # a reused pid must not be killed
            prog.write_text(json.dumps(data))
            self.run_disks("cancelinstall", slug)
            time.sleep(0.3)
            self.assertIsNone(sleeper.poll())
        finally:
            sleeper.kill()

    def test_parallel_adds_keep_every_game(self):
        src = Path(self.tmp.name) / "P"
        src.mkdir()
        (src / "a.exe").write_bytes(b"MZ")
        procs = [subprocess.Popen([sys.executable, str(SCRIPTS / "disks.py"), "add",
                                   json.dumps({"kind": "ready", "path": str(src), "title": f"Game {i}"})],
                                  env=self.env, stdout=subprocess.DEVNULL) for i in range(8)]
        for p in procs:
            p.wait(timeout=60)
        time.sleep(3)
        state = json.loads((self.runtime / "disks" / "state.json").read_text())
        self.assertEqual(len(state["games"]), 8)

    def test_folder_copy_checks_free_space(self):
        src = Path(self.tmp.name) / "Big"
        src.mkdir()
        (src / "g.exe").write_bytes(b"MZ" * 5000)
        env = dict(self.env, SK_DISKS_FAKE_FREE="100")
        out = subprocess.run([sys.executable, str(SCRIPTS / "disks.py"), "add",
                              json.dumps({"kind": "ready", "path": str(src), "title": "Big"})],
                             capture_output=True, text=True, env=env, timeout=60)
        slug = json.loads(out.stdout.strip().splitlines()[-1])["Content"]["ShortName"]
        for _ in range(100):
            prog = self.run_disks("getprogress", slug)["Content"]
            if prog.get("Error"):
                break
            time.sleep(0.1)
        self.assertIn("free space", prog["Error"])
        self.assertFalse((self.home / "Games" / "Disques" / slug).exists())

    def test_quote_in_exe_path_is_refused(self):
        src = Path(self.tmp.name) / "Q"
        src.mkdir()
        (src / 'odd"name.exe').write_bytes(b"MZ")
        slug = self.add("ready", src, "Q")
        self.wait_stage(slug)
        bad = str(Path(json.loads((self.runtime / "disks" / "state.json").read_text())["games"][slug]["root"])
                  / "game" / 'odd"name.exe')
        res = self.run_disks("setexe", slug, bad)
        self.assertEqual(res["Type"], "Error")

    def test_dead_worker_reports_an_error(self):
        state_path = self.runtime / "disks" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"games": {"ghost": {"title": "Ghost", "slug": "ghost",
                                          "stage": "preparing", "root": "/nonexistent/ghost",
                                          "created": time.time() - 120}}, "last_scan_dir": ""}))
        prog = self.runtime / "disks" / "progress"
        prog.mkdir(parents=True, exist_ok=True)
        (prog / "ghost.json").write_text(json.dumps({"Percentage": 5, "Description": "x", "Error": None,
                                                     "pid": 999999}))
        res = self.run_disks("getprogress", "ghost")
        self.assertTrue(res["Content"]["Error"])

    def test_cancel_cleans_up(self):
        src = Path(self.tmp.name) / "Ready"
        src.mkdir()
        (src / "a.exe").write_bytes(b"MZ")
        slug = self.add("folder", src, "Ready")
        g = self.wait_stage(slug)
        self.run_disks("cancelinstall", slug)
        self.assertFalse(Path(g["root"]).exists())
        state = json.loads((self.runtime / "disks" / "state.json").read_text())
        self.assertNotIn(slug, state["games"])
        self.assertTrue(src.exists())

    def test_add_duplicate_title_gets_suffix(self):
        src = Path(self.tmp.name) / "R"
        src.mkdir()
        (src / "a.exe").write_bytes(b"MZ")
        a = self.add("folder", src, "Same")
        self.wait_stage(a)
        b = self.add("folder", src, "Same")
        self.assertEqual((a, b), ("same", "same-2"))

    def test_scan_remembers_folder(self):
        d = Path(self.tmp.name) / "Downloads"
        d.mkdir()
        (d / "setup_x.exe").write_bytes(b"MZ")
        res = self.run_disks("scan", str(d))
        self.assertEqual(res["Type"], "DiskScan")
        self.assertEqual(len(res["Content"]["entries"]), 1)
        self.assertEqual(self.run_disks("sources")["Content"]["last_scan_dir"], str(d))


if __name__ == "__main__":
    unittest.main()
