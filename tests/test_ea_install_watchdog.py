"""EA installs stuck at 99 % behind a process left open in Maxima's prefix (#10)."""
import os
import signal
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts" / "Extensions" / "EA"))

import ea

GAME = "/run/media/deck/SSD/SkullKey/ea/battlefield-2142"
WIN = "z:\\run\\media\\deck\\ssd\\skullkey\\ea\\battlefield-2142"
INFRA = [(10, "wineserver", ""), (11, "services.exe", "c:\\windows\\system32\\services.exe"),
         (12, "steam.exe", "c:\\windows\\system32\\steam.exe")]


def watchdog():
    with mock.patch.object(ea, "root", return_value=Path("/nonexistent")):
        return ea.InstallWatchdog(GAME)


class SortTest(unittest.TestCase):
    def test_processes_are_sorted_by_role(self):
        dog = watchdog()
        touchup, leftovers, infra, others = ea.sort_processes(INFRA + [
            (20, "touchup.exe", WIN + "\\__installer\\touchup.exe install"),
            (21, "dxsetup.exe", "dxsetup.exe /silent"),
            (22, "cleanup.exe", WIN + "\\cleanup.exe"),
            (23, "jedi.exe", "z:\\games\\jedi\\jedi.exe"),
        ], dog.places)
        self.assertEqual([p for p, _ in touchup], [20])
        self.assertEqual([p for p, _ in leftovers], [21, 22])
        self.assertEqual([p for p, _ in infra], [10, 11, 12])
        self.assertEqual([p for p, _ in others], [23])


class CheckTest(unittest.TestCase):
    def run_check(self, dog, processes, silent):
        with mock.patch.object(ea, "prefix_processes", return_value=processes), \
                mock.patch.object(ea.os, "kill") as kill:
            return dog.check(silent), kill

    def test_touchup_still_running_is_left_alone(self):
        dog = watchdog()
        note, kill = self.run_check(dog, INFRA + [(20, "touchup.exe", "")], 600)
        self.assertEqual(note, ea.INSTALLER_WAITING)
        kill.assert_not_called()
        note, kill = self.run_check(dog, INFRA + [(20, "touchup.exe", "")], 900)
        self.assertIsNone(note)

    def test_leftover_redistributable_is_closed_then_killed(self):
        dog = watchdog()
        leftover = INFRA + [(21, "dxsetup.exe", "dxsetup.exe")]
        self.assertEqual(self.run_check(dog, leftover, 30)[0], None)
        note, kill = self.run_check(dog, leftover, 75)
        self.assertEqual(note, ea.CLOSING_LEFTOVERS)
        kill.assert_called_once_with(21, signal.SIGTERM)
        self.assertEqual(dog.names, ["dxsetup.exe"])
        _, kill = self.run_check(dog, leftover, 90)
        kill.assert_called_once_with(21, signal.SIGKILL)

    def test_only_wine_left_closes_wine(self):
        dog = watchdog()
        self.assertIsNone(self.run_check(dog, INFRA, 60)[0])
        note, kill = self.run_check(dog, INFRA, 130)
        self.assertEqual(note, ea.CLOSING_LEFTOVERS)
        self.assertEqual(dog.action, "closed-wine-services")
        self.assertEqual(kill.call_count, 3)

    def test_another_program_in_the_prefix_stops_everything(self):
        dog = watchdog()
        running = INFRA + [(21, "dxsetup.exe", ""), (23, "jedi.exe", "z:\\games\\jedi\\jedi.exe")]
        note, kill = self.run_check(dog, running, 400)
        self.assertIsNone(note)
        kill.assert_not_called()
        self.assertEqual(dog.names, ["jedi.exe"])

    def test_nothing_running_does_nothing(self):
        note, kill = self.run_check(watchdog(), [], 900)
        self.assertIsNone(note)
        kill.assert_not_called()


class ProcTest(unittest.TestCase):
    def test_reads_real_processes_without_error(self):
        # This test's own process has no WINEPREFIX of that name.
        with mock.patch.dict(os.environ, {"WINEPREFIX": "/elsewhere"}):
            self.assertEqual(list(ea.prefix_processes("/nonexistent/prefix")), [])


if __name__ == "__main__":
    unittest.main()
