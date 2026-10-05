"""Execute the embedded loader with an isolated Python module cache."""
import builtins
from pathlib import Path
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "android/app/src/main/java/com/tsbot/android/BotForegroundService.kt"


class LoadedCoreVersionTests(unittest.TestCase):
    def run_loader(self, purge, previous="old", fail_import=False):
        source = SOURCE.read_text(encoding="utf-8")
        code = source.split('val code = """', 1)[1].split('""".trimIndent()', 1)[0]
        code = code.replace('${\'"\'}', '"')
        code = code.replace('$coreVer', 'new').replace('$p', '/bundle')
        code = code.replace('${BuildConfig.VERSION_NAME}', 'apk')
        code = code.replace('${if (purge) "True" else "False"}', str(purge))
        state = SimpleNamespace(path=['/apk'], modules={'train_bot.client': object()})
        if previous is not None:
            state.__ats_core_loaded__ = previous
        package = SimpleNamespace(client=SimpleNamespace(__file__='/bundle/client.py'))
        original_import = builtins.__import__

        def isolated_import(name, *args, **kwargs):
            if name == 'sys':
                return state
            if name == 'train_bot.client':
                if fail_import:
                    raise ImportError('broken bundle')
                return package
            return original_import(name, *args, **kwargs)

        env = {'__builtins__': dict(vars(builtins), __import__=isolated_import)}
        try:
            exec(code, env)
        except ImportError:
            if not fail_import:
                raise
        return state

    def test_active_bot_keeps_loaded_version_and_search_path(self):
        state = self.run_loader(False)
        self.assertEqual(state.__ats_core_loaded__, 'old')
        self.assertEqual(state.path, ['/apk'])
        self.assertIn('train_bot.client', state.modules)

    def test_unrecorded_active_runtime_does_not_claim_downloaded_version(self):
        state = self.run_loader(False, previous=None)
        self.assertNotEqual(getattr(state, '__ats_core_loaded__', None), 'new')

    def test_idle_success_records_new_version(self):
        state = self.run_loader(True)
        self.assertEqual(state.__ats_core_loaded__, 'new')
        self.assertEqual(state.path[0], '/bundle')
        self.assertNotIn('train_bot.client', state.modules)

    def test_failed_reload_does_not_claim_success_or_old_runtime(self):
        state = self.run_loader(True, fail_import=True)
        self.assertIsNone(getattr(state, '__ats_core_loaded__', None))


if __name__ == '__main__':
    unittest.main()
