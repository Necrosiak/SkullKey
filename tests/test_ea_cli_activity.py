"""Progress heartbeats must not postpone the install watchdog indefinitely."""
import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import patch

class CliActivityTests(unittest.TestCase):
    def module(self):
        p=Path(__file__).resolve().parents[1]/'defaults/scripts/Extensions/EA/ea.py'
        s=importlib.util.spec_from_file_location('ea_activity_fixture',p)
        m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

    def test_repeated_and_backwards_progress_do_not_count_as_work(self):
        ea=self.module();now=[0]
        with patch.object(ea,'time',types.SimpleNamespace(monotonic=lambda:now[0])):
            activity=ea.InstallActivity();now[0]=10;activity.observe('Progress: 100.00')
            for value in ('100','100.00','99.99'):
                now[0]+=60;activity.observe('Progress: '+value)
            self.assertEqual(activity.last_activity,10)

    def test_real_progress_and_new_status_reset_idle_time(self):
        ea=self.module();now=[0]
        with patch.object(ea,'time',types.SimpleNamespace(monotonic=lambda:now[0])):
            a=ea.InstallActivity();now[0]=10;a.observe('Progress: 99')
            now[0]=20;a.observe('Progress: 100');self.assertEqual(a.last_activity,20)
            now[0]=30;a.observe('Touchup setup started');self.assertEqual(a.last_activity,30)

    def test_timestamps_and_alternating_status_heartbeats_do_not_reset_idle(self):
        ea=self.module();now=[0]
        with patch.object(ea,'time',types.SimpleNamespace(monotonic=lambda:now[0])):
            a=ea.InstallActivity()
            for i,line in enumerate(('2026-10-29T10:00:00Z INFO Waiting','2026-10-29T10:00:01Z INFO Pending','2026-10-29T10:10:00Z INFO Waiting','2026-10-29T10:10:01Z INFO Pending')):
                now[0]=i+1;a.observe(line)
            self.assertEqual(a.last_activity,2)

    def test_status_history_is_bounded_and_does_not_store_log_text(self):
        ea=self.module();a=ea.InstallActivity()
        for i in range(150):a.observe('synthetic-private-status-'+str(i))
        self.assertEqual(len(a.signatures),128)
        self.assertNotIn('synthetic-private-status',repr(a.signatures))

if __name__=='__main__':unittest.main()
