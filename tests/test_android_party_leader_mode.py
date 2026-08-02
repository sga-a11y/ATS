import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "android/app/src/main/java/com/tsbot/android/BotForegroundService.kt"


class TestAndroidPartyLeaderMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = SERVICE.read_text(encoding="utf-8")
        match = re.search(
            r"private fun mapMode\(party: Party\): ModeCfg = when \(party\.runMode\) \{(.*?)\n    \}",
            source,
            re.DOTALL,
        )
        assert match is not None
        cls.map_mode = match.group(1)

    def test_digioi_train_maps_to_party_mode_with_selected_train_target(self):
        self.assertRegex(
            self.map_mode,
            r'(?s)RunModes\.DIGIOI_TRAIN\s*->\s*ModeCfg\(\s*"digioi_train",'
            r'.*?party\.trainMapKey\.toIntOrNull\(\)\s*\?:\s*0,'
            r'.*?party\.trainMobIndex,.*?"party",\s*!party\.noLeader,',
        )


if __name__ == "__main__":
    unittest.main()
