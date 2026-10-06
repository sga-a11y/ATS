import importlib.util
from pathlib import Path
from types import SimpleNamespace
import threading
import unittest


PATH = Path(__file__).resolve().parents[1] / 'android/app/src/main/python/core_update_runtime.py'


class CoreUpdateRuntimeTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('core_update_runtime_test', PATH)
        self.runtime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.runtime)

    def test_stop_and_join_before_allowing_reload(self):
        stopped = threading.Event()
        worker = threading.Thread(target=stopped.wait)
        worker.start()
        controller = threading.Thread(target=stopped.wait)
        controller.start()
        engine = SimpleNamespace(_th=controller, workers={}, stop=stopped.set)
        core = SimpleNamespace(account_threads={'active': worker}, account_stops={},
                               _party_engines={0: engine}, stop_all=lambda **kw: stopped.set())
        try:
            self.assertEqual(self.runtime.quiesce(core, timeout=1), ['active'])
            self.assertFalse(worker.is_alive())
            self.assertFalse(controller.is_alive())
        finally:
            stopped.set()
            worker.join()
            controller.join()

    def test_timeout_blocks_reload(self):
        thread = SimpleNamespace(is_alive=lambda: True, join=lambda timeout: None)
        core = SimpleNamespace(account_threads={'stuck': thread}, account_stops={},
                               _party_engines={}, stop_all=lambda **kw: None)
        with self.assertRaisesRegex(RuntimeError, 'chưa dừng'):
            self.runtime.quiesce(core, timeout=0)

    def test_manually_stopped_accounts_are_not_resumed(self):
        stop = threading.Event()
        stop.set()
        alive = [True]
        thread = SimpleNamespace(is_alive=lambda: alive[0], join=lambda timeout: None)
        core = SimpleNamespace(account_threads={'stopped': thread}, account_stops={'stopped': stop},
                               _party_engines={}, stop_all=lambda **kw: alive.__setitem__(0, False))
        self.assertEqual(self.runtime.quiesce(core), [])

    def test_restore_old_modules_after_failed_import(self):
        old = object()
        state = SimpleNamespace(modules={'train_bot': old, 'other': object()}, path=['apk'],
                                __ats_core_loaded__='old')
        snapshot = self.runtime.capture(state)
        state.modules['train_bot'] = object()
        state.modules['train_bot.broken'] = object()
        state.path.insert(0, 'new')
        state.__ats_core_loaded__ = None
        self.runtime.restore(snapshot, state)
        self.assertIs(state.modules['train_bot'], old)
        self.assertNotIn('train_bot.broken', state.modules)
        self.assertEqual(state.path, ['apk'])
        self.assertEqual(state.__ats_core_loaded__, 'old')
