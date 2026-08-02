import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "android/app/src/main/java/com/tsbot/android/MainActivity.kt").read_text(encoding="utf-8")
STORE = (ROOT / "android/app/src/main/java/com/tsbot/android/PartyStore.kt").read_text(encoding="utf-8")


class TestAndroidPartyNameValidation(unittest.TestCase):
    def test_empty_party_name_shows_inline_error_instead_of_silent_noop(self):
        self.assertIn("var nameError by remember", UI)
        self.assertIn("isError = nameError != null", UI)
        self.assertIn('nameError = "Vui lòng nhập tên party"', UI)

    def test_duplicate_party_name_is_reported_and_dialog_stays_open(self):
        self.assertIn('nameError = "Tên party đã tồn tại"', UI)
        self.assertIn("if (!saved)", UI)
        self.assertIn("onSave: (Party) -> Boolean", UI)

    def test_party_store_rejects_duplicate_instead_of_replacing_existing_party(self):
        self.assertIn("fun addParty(party: Party): Boolean", STORE)
        self.assertIn("equals(party.name.trim(), ignoreCase = true)", STORE)
        self.assertNotIn("load().filterNot { it.name == party.name }", STORE)


if __name__ == "__main__":
    unittest.main()
