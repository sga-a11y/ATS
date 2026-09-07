"""TEN PET hien kem CAP: `Ten_lv` (vd `Quan Vu_111`).

User chot 07/09: nha tro (van tieu) / battle / tui do deu phai thay cap, de soat con nao chua nuoi
ma khong phai mo tung con ra xem.

Cap co san o CA HAI nguon, khong phai doan:

  - Pet MANG THEO - `S2C 0x0f sub08`, byte +7 cua tung record (bot da doc san cho
    `_pet_skill_rows` va `pet_login_records[marker]["level"]`).
  - Pet NHA TRO - `protocal.lua:6798`:
        S:031-006 <客棧武將資料> +客棧索引(1) +NPCID(2) +等級(1) +HP(4) +L(1) +名字(L) +武將狀態(1)
    tuc cap nam ngay sau NPCID (+3). (Vi tri cua L thi bot do thuc nghiem ra +12, lech 4 byte so
    voi mo ta - giu nguyen cai da chay dung, chi lay them cap.)

Ghep cap vao TEN ngay tai nguon (`carried_pets`, `vantieu_roster`) thay vi sua tung cho hien:
ten pet o cac cho do CHI de hien, moi cho so khop deu dung `pid`. Nho vay tui do (PC), tab battle
(PC + APK), dialog van tieu (PC + APK) va ca cache luc acc TAT deu co cap ma chi sua mot noi.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import ten_pet_kem_lv   # noqa: E402


def _src(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class TestNhan(unittest.TestCase):
    def test_dang_ten_gach_duoi_lv(self):
        self.assertEqual(ten_pet_kem_lv("Quan Vũ", 111), "Quan Vũ_111")

    def test_cap_khong_hop_le_thi_giu_ten_tran(self):
        """Khong duoc bia so - acc TAT / pet chua co du lieu thi chua biet cap."""
        for lv in (0, None, "", -1, 201, 999, "x"):
            self.assertEqual(ten_pet_kem_lv("Quan Vũ", lv), "Quan Vũ", repr(lv))

    def test_ten_rong_thi_van_rong(self):
        self.assertEqual(ten_pet_kem_lv("", 111), "")
        self.assertEqual(ten_pet_kem_lv(None, 111), "")

    def test_bien_hai_dau_bi_cat(self):
        self.assertEqual(ten_pet_kem_lv("  Quan Vũ  ", 111), "Quan Vũ_111")


class TestGhepTaiNguon(unittest.TestCase):
    def test_carried_pets_ghep_cap(self):
        s = _src("bot", "client.py")
        i = s.find("self.state.carried_pets.append(")
        self.assertGreater(i, 0)
        self.assertIn("ten_pet_kem_lv(", s[i:i + 260], "carried_pets van luu ten tran")

    def test_cap_pet_mang_theo_doc_tu_byte_7(self):
        s = _src("bot", "client.py")
        i = s.find("self.state.carried_pets.append(")
        khoi = s[max(0, i - 700):i]
        self.assertIn("b[start + 7]", khoi)

    def test_van_tieu_ghep_cap(self):
        s = _src("bot", "client.py")
        i = s.find("moi[index] = ")
        self.assertGreater(i, 0)
        self.assertIn("ten_pet_kem_lv(", s[i:i + 120], "roster nha tro van luu ten tran")

    def test_cap_nha_tro_doc_dung_offset_client(self):
        """`+客棧索引(1) +NPCID(2) +等級(1)` -> cap o +3, ngay sau NPCID."""
        s = _src("bot", "client.py")
        i = s.find("npc_lv = b[pos + 3]")
        self.assertGreater(i, 0, "chua doc cap tu goi nha tro")
        self.assertIn("S:031-006", s[max(0, i - 500):i], "thieu vien dan goi client")


class TestChoHienThi(unittest.TestCase):
    def test_tab_battle_PC_ghep_cap(self):
        """Tab battle lay ten tu PET_NAMES (khong qua carried_pets) nen phai tu ghep."""
        s = _src("gui.py")
        i = s.find("def _pet_tab_title(pid):")
        self.assertGreater(i, 0)
        self.assertIn("ten_pet_kem_lv(", s[i:i + 500])

    def test_tui_do_PC_dung_carried_pets(self):
        """Tui do doc thang `carried_pets` -> khong phai sua gi, nhung phai GIU duong do."""
        s = _src("gui.py")
        i = s.find("def _pet_list(self):")
        self.assertGreater(i, 0)
        self.assertIn("carried_pets", s[i:i + 600])

    def test_APK_an_theo_python(self):
        """APK lay ten pet qua chinh Python (`skills_snapshot` cho tab battle, `account_inn_pets`
        cho van tieu) nen tu co cap - khong duoc dung ten tu bang Kotlin rieng."""
        s = _src("bot", "client.py")
        i = s.find("def skills_snapshot(st):")
        self.assertGreater(i, 0)
        self.assertIn("carried_pets", s[i:i + 800])
        r = _src("run_party_digioi.py")
        j = r.find("def account_inn_pets(username):")
        self.assertGreater(j, 0)
        self.assertIn("vantieu_roster", r[j:j + 900])


if __name__ == "__main__":
    unittest.main()
