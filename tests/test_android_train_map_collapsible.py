import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "android/app/src/main/java/com/tsbot/android/MainActivity.kt").read_text(encoding="utf-8")


class TestAndroidTrainMapCollapsible(unittest.TestCase):
    def test_train_map_groups_can_be_collapsed_without_closing_menu(self):
        self.assertIn("nhomDangGap", UI)
        # NEO THEO Y NGHIA, khong theo dang chu. Da doi hai lan:
        #   - truoc day neo y nguyen dong "if (g !in collapsedTrainMapGroups)";
        #   - 23/09 danh sach map chuyen han sang DIALOG RIENG (`TrainMapDialog`) vi popup neo vao
        #     anchor trong `Column(verticalScroll)` bi lech khi ban phim mo - xem
        #     `tests/test_android_chon_map_train_bam_duoc.py`. State doi ten thanh `nhomDangGap`.
        # Luat khong doi: co quyet dinh GAP tu tap, noi dung nhom chi ve khi KHONG gap, va bam vao
        # nhom la TOGGLE chu khong dong danh sach.
        self.assertRegex(UI, r"val gap = .*g in nhomDangGap")
        self.assertIn("if (!gap) {", UI)
        self.assertRegex(UI, r"nhomDangGap = if \(gap\) nhomDangGap - g else nhomDangGap \+ g")


if __name__ == "__main__":
    unittest.main()
