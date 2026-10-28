import hashlib
import io
import json
import os
import sys
import tarfile
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))


def make_archive(path, top, files):
    with tarfile.open(path, "w:xz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(f"{top}/{name}")
            info.size = len(data)
            info.mode = 0o755
            tar.addfile(info, io.BytesIO(data))
    return hashlib.sha512(Path(path).read_bytes()).hexdigest()


def release(tag, *names, prerelease=False):
    return {"tag_name": tag, "prerelease": prerelease, "draft": False,
            "assets": [{"name": n, "browser_download_url": "https://github.com/x/" + n} for n in names]}


RELEASES = [
    release("v0.3.10", "Xodus-Nexus-0.3.10-x86_64.AppImage", "Xodus-Nexus-0.3.10-x86_64.AppImage.sha512sum"),
    release("backend-v0.2.10", "xodus-nexus-backend-0.2.10-linux-x86_64-source.tar.xz",
            "xodus-nexus-backend-0.2.10-linux-x86_64.tar.xz", "xodus-nexus-backend-0.2.10-linux-x86_64.sha512sum"),
    release("runtime-11.0-20261020-gabc", "xodus-nexus-runtime-11.0-20261020-gabc-x86_64.tar.xz",
            "xodus-nexus-runtime-11.0-20261020-gabc-x86_64.sha512sum"),
    release("backend-v0.2.9", "xodus-nexus-backend-0.2.9-linux-x86_64.tar.xz",
            "xodus-nexus-backend-0.2.9-linux-x86_64.sha512sum"),
]


class ToolsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["DECKY_PLUGIN_RUNTIME_DIR"] = self.tmp.name
        import importlib
        import xbox_tools
        self.t = importlib.reload(xbox_tools)
        self.src = Path(self.tmp.name) / "src"
        self.src.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def serve(self, files):
        """files: asset name -> bytes; returns a download(url, dest) fake."""
        def download(url, dest):
            Path(dest).write_bytes(files[url.rsplit("/", 1)[1]])
        return download

    def backend_files(self, version="0.2.10", good=True):
        name = f"xodus-nexus-backend-{version}-linux-x86_64.tar.xz"
        arc = self.src / name
        digest = make_archive(arc, name[:-7], {"xodus-cli": b"#!/bin/sh\n", "xodus-service": b"x", "LICENSE": b"GPL"})
        if not good:
            digest = "0" * 128
        return {name: arc.read_bytes(),
                name[:-7] + ".sha512sum": f"{digest}  {name}\n".encode()}

    def test_latest_picks_newest_per_family(self):
        r = self.t.latest_releases(fetch=lambda url: RELEASES)
        self.assertEqual(r["backend"][0], "backend-v0.2.10")
        self.assertEqual(r["runtime"][0], "runtime-11.0-20261020-gabc")
        self.assertEqual(r["launcher"][0], "v0.3.10")

    def test_source_assets_ignored(self):
        r = self.t.latest_releases(fetch=lambda url: RELEASES)
        archive, _ = self.t.pick_assets("backend", r["backend"][1])
        self.assertNotIn("-source", archive["name"])

    def test_install_extracts_and_writes_current(self):
        path = self.t.install_component("backend", fetch=lambda u: RELEASES, download=self.serve(self.backend_files()))
        self.assertTrue((path / "xodus-cli").exists())
        self.assertEqual(self.t.cli_path(), path / "xodus-cli")
        self.assertEqual(self.t.current("backend")["version"], "backend-v0.2.10")

    def test_sha_mismatch_keeps_previous_version(self):
        old = self.t.install_component("backend", fetch=lambda u: RELEASES,
                                       download=self.serve(self.backend_files()))
        bad = [release("backend-v0.2.11", "xodus-nexus-backend-0.2.11-linux-x86_64.tar.xz",
                       "xodus-nexus-backend-0.2.11-linux-x86_64.sha512sum")]
        with self.assertRaises(self.t.ToolsError):
            self.t.install_component("backend", fetch=lambda u: bad,
                                     download=self.serve(self.backend_files("0.2.11", good=False)))
        self.assertEqual(self.t.cli_path(), old / "xodus-cli")

    def test_no_update_while_busy(self):
        with self.t.hold("install-x"):
            self.assertTrue(self.t.busy())
            with mock.patch.object(self.t, "install_component") as inst:
                self.t.ensure(update=True, components=("backend",), present=lambda k: True)
                inst.assert_not_called()

    def test_update_throttled_6h(self):
        with mock.patch.object(self.t, "install_component") as inst, \
             mock.patch.object(self.t, "latest_releases", return_value={"backend": ("backend-v9", [])}):
            self.t.ensure(update=True, components=("backend",), present=lambda k: True)
            self.t.ensure(update=True, components=("backend",), present=lambda k: True)
            self.assertEqual(inst.call_count, 1)

    def test_missing_component_installed_even_when_throttled(self):
        (self.t.XBOX_DIR / "cache").mkdir(parents=True, exist_ok=True)
        (self.t.XBOX_DIR / "cache" / "last-check").write_text(str(time.time()))
        with mock.patch.object(self.t, "install_component") as inst:
            self.t.ensure(update=True, components=("backend",), present=lambda k: False)
            inst.assert_called_once()

    def test_file_keychain_engine_preferred(self):
        self.t.install_component("backend", fetch=lambda u: RELEASES, download=self.serve(self.backend_files()))
        own = self.t.XBOX_DIR / "engine-file-keychain"
        own.mkdir(parents=True)
        for name in ("xodus-cli", "xodus-service"):
            (own / name).write_text("#!/bin/sh")
        self.assertEqual(self.t.cli_path(), own / "xodus-cli")
        self.assertEqual(self.t.service_path(), own / "xodus-service")
        self.assertTrue(self.t.present("backend"))

    def test_own_engine_downloaded_and_checked(self):
        arc = self.src / self.t.OWN_ENGINE_ASSET
        digest = make_archive(arc, "xodus-engine-skullkey", {"xodus-cli": b"#!/bin/sh\n", "xodus-service": b"x", "LICENSE": b"GPL"})
        with mock.patch.object(self.t, "OWN_ENGINE_SHA512", digest):
            self.t.install_own_engine(download=lambda url, dest: Path(dest).write_bytes(arc.read_bytes()))
        self.assertEqual(self.t.cli_path(), self.t.XBOX_DIR / self.t.OWN_ENGINE / "xodus-cli")

    def test_own_engine_with_wrong_checksum_refused(self):
        arc = self.src / self.t.OWN_ENGINE_ASSET
        make_archive(arc, "xodus-engine-skullkey", {"xodus-cli": b"evil"})
        with self.assertRaises(self.t.ToolsError):
            self.t.install_own_engine(download=lambda url, dest: Path(dest).write_bytes(arc.read_bytes()))
        self.assertFalse((self.t.XBOX_DIR / self.t.OWN_ENGINE / "xodus-cli").exists())

    def test_ensure_installs_own_engine_first(self):
        def fake_own():
            d = self.t.XBOX_DIR / self.t.OWN_ENGINE
            d.mkdir(parents=True)
            (d / "xodus-cli").write_text("x")
        with mock.patch.object(self.t, "install_own_engine", side_effect=fake_own) as own, \
             mock.patch.object(self.t, "install_component") as official:
            self.t.ensure(update=False, components=("backend",))
        own.assert_called_once()
        official.assert_not_called()

    def test_official_engine_is_the_fallback(self):
        with mock.patch.object(self.t, "install_own_engine", side_effect=self.t.ToolsError("offline")), \
             mock.patch.object(self.t, "install_component") as official:
            self.t.ensure(update=False, components=("backend",))
        official.assert_called_once_with("backend")

    def runtime_release(self, tag, name, date):
        return dict(release(tag, name + "-x86_64.tar.xz", name + "-x86_64.sha512sum"), published_at=date)

    def test_runtime_from_new_repository_by_date(self):
        new = [self.runtime_release("runtime-11.0-20261026-gbbb", "nexus-runtime-11.0-experimental-gbbb", "2026-10-26T10:00:00Z"),
               self.runtime_release("runtime-11.0-20261024-gfff", "nexus-runtime-11.0-experimental-gfff", "2026-10-24T10:00:00Z"),
               dict(release("runtime-11.0-20261027-gccc", "nexus-runtime-11.0-experimental-gccc-x86_64.tar.xz"),
                    published_at="2026-10-27T10:00:00Z")]  # no checksum: skipped
        fetch = lambda url: new if "nexus-runtime/" in url else RELEASES
        r = self.t.latest_releases(fetch=fetch)
        self.assertEqual(r["runtime"][0], "runtime-11.0-20261026-gbbb")
        self.assertEqual(r["backend"][0], "backend-v0.2.10")

    def test_runtime_falls_back_to_main_repository(self):
        def fetch(url):
            if "nexus-runtime/" in url:
                raise OSError("404")
            return RELEASES
        self.assertEqual(self.t.latest_releases(fetch=fetch)["runtime"][0], "runtime-11.0-20261020-gabc")

    def test_runtime_needing_newer_engine_keeps_previous(self):
        own = self.t.XBOX_DIR / self.t.OWN_ENGINE
        own.mkdir(parents=True)
        (own / "xodus-cli").write_text("x")
        (own / "BUILD-METADATA.json").write_text(json.dumps({"source_tag": "backend-v0.2.11"}))
        name = "nexus-runtime-11.0-experimental-gbbb-x86_64.tar.xz"
        arc = self.src / name
        meta = json.dumps({"requiresBackendVersion": "0.2.12"}).encode()
        digest = make_archive(arc, name[:-7], {"XODUS_NEXUS_PATCH.json": meta, "proton": b"x"})
        rels = [self.runtime_release("runtime-11.0-20261026-gbbb", name[:-14], "2026-10-26T10:00:00Z")]
        files = {name: arc.read_bytes(), name[:-7] + ".sha512sum": f"{digest}  {name}\n".encode()}
        fetch = lambda url: rels if "nexus-runtime/" in url else []
        with self.assertRaises(self.t.ToolsError):
            self.t.install_component("runtime", fetch=fetch, download=self.serve(files))
        self.assertIsNone(self.t.current("runtime"))
        (own / "BUILD-METADATA.json").write_text(json.dumps({"source_tag": "backend-v0.2.12"}))
        self.t.install_component("runtime", fetch=fetch, download=self.serve(files))
        self.assertEqual(self.t.current("runtime")["version"], "runtime-11.0-20261026-gbbb")

    def test_outdated_own_engine_replaced_once_per_6h_on_failure(self):
        own = self.t.XBOX_DIR / self.t.OWN_ENGINE
        own.mkdir(parents=True)
        (own / "xodus-cli").write_text("x")
        (own / "BUILD-METADATA.json").write_text(json.dumps({"source_tag": "backend-v0.2.10"}))
        with mock.patch.object(self.t, "install_own_engine", side_effect=self.t.ToolsError("offline")) as inst, \
             mock.patch.object(self.t, "latest_releases", return_value={}):
            r = self.t.ensure(update=True, components=("backend",), present=lambda k: True)
            self.t.ensure(update=True, components=("backend",), present=lambda k: True)
        self.assertEqual(inst.call_count, 1)
        self.assertEqual(r["errors"], ["offline"])

    def test_current_own_engine_not_downloaded_again(self):
        own = self.t.XBOX_DIR / self.t.OWN_ENGINE
        own.mkdir(parents=True)
        (own / "xodus-cli").write_text("x")
        tag = "backend-v" + ".".join(map(str, self.t.OWN_ENGINE_VERSION))
        (own / "BUILD-METADATA.json").write_text(json.dumps({"source_tag": tag}))
        with mock.patch.object(self.t, "install_own_engine") as inst, \
             mock.patch.object(self.t, "latest_releases", return_value={}):
            self.t.ensure(update=True, components=("backend",), present=lambda k: True)
        inst.assert_not_called()

    def test_dead_lock_pid_not_busy(self):
        locks = self.t.XBOX_DIR / "locks"
        locks.mkdir(parents=True)
        (locks / "run-x").write_text("999999")
        self.assertFalse(self.t.busy())


if __name__ == "__main__":
    unittest.main()
