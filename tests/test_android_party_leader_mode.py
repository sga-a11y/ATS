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
        """DIGIOI_TRAIN phai ra mode "digioi_train", di kem MUC TIEU TRAIN va co leader theo party.

        Tinh nang trainPick (chon NHIEU bai) doi 2 truong nay thanh co dieu kien:
            if (party.trainPick.isEmpty()) party.trainMapKey.toIntOrNull() ?: 0 else 0
            if (party.trainPick.isEmpty()) party.trainMobIndex else -1
        Test cu neo vao dang CU nen do sau khi pull. Neo lai theo Y NGHIA: van phai co ca
        trainMapKey, trainMobIndex va co leader - khong quan tam boc trong `if` hay khong.
        """
        i = self.map_mode.index("RunModes.DIGIOI_TRAIN")
        khoi = self.map_mode[i:i + 400]
        self.assertIn('ModeCfg(', khoi)
        self.assertIn('"digioi_train"', khoi)
        self.assertIn("party.trainMapKey.toIntOrNull()", khoi, "mat muc tieu map train")
        self.assertIn("party.trainMobIndex", khoi, "mat muc tieu bai quai")
        self.assertIn('"party"', khoi)
        self.assertIn("!party.noLeader", khoi, "mat co leader theo party")

    def test_TRAIN_va_DIGIOI_TRAIN_dung_CUNG_cach_chon_muc_tieu(self):
        """Hai mode nay phai chon muc tieu giong het nhau - lech la mot mode di sai bai."""
        def _khoi(ten):
            i = self.map_mode.index("RunModes.%s ->" % ten)
            j = self.map_mode.index("RunModes.", i + 10)
            return self.map_mode[i:j]

        def _chuan(s):
            # cat DUNG phan sau dau "->" (khong cat theo do dai co dinh: ten mode dai ngan khac nhau)
            return " ".join(s.split()).split("->", 1)[1]

        dt = _chuan(_khoi("DIGIOI_TRAIN")).replace('"digioi_train"', "X")
        tr = _chuan(_khoi("TRAIN")).replace('"train"', "X")
        self.assertEqual(dt.strip().rstrip(","), tr.strip().rstrip(","),
                         "TRAIN va DIGIOI_TRAIN chon muc tieu KHAC nhau")


if __name__ == "__main__":
    unittest.main()
