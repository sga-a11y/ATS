"""Applying a core restarts the bot process: never automatically while accounts are running.

User chot 06/10: dang co acc chay (pho ban, boss...) thi KHONG tu ap dung core moi, chi bao va cho
user bam "Ap dung ngay". Test device (tools/test_android_core_restart.py) goi thang installBundleZip
nen khong phu cong nay -> giu bang doc thang Kotlin.
"""
from pathlib import Path
import re
import unittest

ANDROID = Path(__file__).resolve().parents[1] / "android/app/src/main/java/com/tsbot/android"


def read(name):
    return (ANDROID / name).read_text(encoding="utf-8")


def function_body(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for i in range(brace, len(source)):
        depth += {"{": 1, "}": -1}.get(source[i], 0)
        if depth == 0:
            return source[brace:i + 1]
    raise AssertionError("unterminated " + signature)


class CoreUpdateGateTests(unittest.TestCase):
    def test_update_checks_running_accounts_before_downloading(self):
        body = function_body(read("ApkUpdater.kt"), "fun updateBundleIfNeeded(")
        gate = body.index("!applyWhileRunning && hasActiveAccounts?.invoke() == true")
        self.assertLess(gate, body.index("downloadAndInstallBundle("))
        self.assertIn("_deferredCoreVersion.value = info.version", body[gate:body.index("downloadAndInstallBundle(")])

    def test_only_the_apply_now_button_bypasses_the_gate(self):
        sources = {name: read(name) for name in ("MainActivity.kt", "BotForegroundService.kt", "ApkUpdater.kt")}
        bypass = [(name, line.strip()) for name, src in sources.items() for line in src.splitlines()
                  if "applyWhileRunning = true" in line]
        self.assertEqual(len(bypass), 1, bypass)
        self.assertEqual(bypass[0][0], "MainActivity.kt")
        self.assertIn("applyWhileRunning = true", function_body(sources["MainActivity.kt"], "fun applyDeferredCore("))

    def test_service_publishes_running_probe_and_clears_it(self):
        service = read("BotForegroundService.kt")
        self.assertIn("ApkUpdater.hasActiveAccounts = activeAccountsProbe", function_body(service, "override fun onCreate("))
        self.assertIn("ApkUpdater.hasActiveAccounts = null", function_body(service, "override fun onDestroy("))
        start = service.index("private fun hasActiveAccounts(")   # expression body: until blank line
        probe = service[start:service.index("\n\n", start)]
        for part in ("pendingStarts.get() > 0", "startingPidx.isNotEmpty()", '"active_accounts"'):
            self.assertIn(part, probe)

    def test_resume_plan_comes_from_current_saved_parties(self):
        # Review #1: a per-pidx snapshot taken at Start resurrected deleted parties and lost others.
        service = read("BotForegroundService.kt")
        self.assertNotIn("runningParties", service)
        body = function_body(service, "private fun restartForCore(")
        self.assertIn("PartyStore(this).load().map { party ->", body)
        self.assertIn("it.copy(enabled = it.username in active)", body)

    def test_quiesce_outlasts_the_stop_watchdog(self):
        # Review #5: members wait for the leader up to the 25s force-close before exiting.
        quiesce = int(re.search(r"QUIESCE_SECONDS = (\d+)", read("BotForegroundService.kt")).group(1))
        root = Path(__file__).resolve().parents[1]
        for path in ("run_party_digioi.py","android/app/src/main/python/train_bot/run_party_digioi.py"):
            source = (root / path).read_text(encoding="utf-8")
            start = source.index("def _force_close_watchdog")
            watchdog = source[start:source.index("FORCE dong socket", start)]
            seconds = int(re.search(r"range\((\d+)\)", watchdog).group(1))
            self.assertGreaterEqual(quiesce, seconds + 15, path)
        self.assertIn('callAttr("quiesce", core, QUIESCE_SECONDS)',
                      function_body(read("BotForegroundService.kt"), "private fun restartForCore("))

    def test_restart_service_restarts_bot_even_if_old_process_is_gone(self):
        source = read("CoreRestartService.kt")
        kill = source.index("Process.killProcess(oldPid)")
        self.assertRegex(source[:kill], r"if \(old != null\) \{\s*SystemClock\.sleep\(500\)\s*$")
        self.assertNotRegex(source, re.compile(r"check\(old != null"))
        self.assertLess(kill, source.index("BotForegroundService::class.java"))


if __name__ == "__main__":
    unittest.main()
