import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = (ROOT / "android/app/src/main/java/com/tsbot/android/Account.kt").read_text(encoding="utf-8")
STORE = (ROOT / "android/app/src/main/java/com/tsbot/android/PartyStore.kt").read_text(encoding="utf-8")
SERVICE = (ROOT / "android/app/src/main/java/com/tsbot/android/BotForegroundService.kt").read_text(encoding="utf-8")
UI = (ROOT / "android/app/src/main/java/com/tsbot/android/MainActivity.kt").read_text(encoding="utf-8")


class TestAndroidAccountEnabled(unittest.TestCase):
    def test_old_accounts_default_to_enabled_and_value_is_persisted(self):
        self.assertIn("val enabled: Boolean = true", ACCOUNT)
        self.assertIn('a.optBoolean("enabled", true)', STORE)
        self.assertIn('ao.put("enabled", a.enabled)', STORE)

    def test_runtime_contains_only_enabled_accounts(self):
        self.assertIn("val activeAccounts = party.accounts.filter { it.enabled }", SERVICE)
        self.assertIn("activeAccounts.joinToString(SEP)", SERVICE)
        self.assertNotIn("val accountsFlat = party.accounts.joinToString(SEP)", SERVICE)

    def test_account_row_has_checkbox_and_party_start_requires_one_enabled_account(self):
        self.assertIn("onEnabledChange: (Boolean) -> Unit", UI)
        self.assertIn("checked = account.enabled", UI)
        self.assertIn("onCheckedChange = onEnabledChange", UI)
        self.assertIn("enabled = party.accounts.any { it.enabled }", UI)


if __name__ == "__main__":
    unittest.main()
