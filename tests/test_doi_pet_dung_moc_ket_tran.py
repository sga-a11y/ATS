"""DOI PET phai lam o MOC KET TRAN - cho duy nhat chac chan `in_battle` da ha.

Do tren log that 21/09: 169.507 lan "doi pet: DANG TRONG TRAN -> hoan" / 908 lan doi duoc
(ti le 187:1). Ba acc bi nang nhat KHONG doi duoc lan nao:

    vutam    20.021 lan hoan / 0 lan doi duoc
    luubmot  18.006 / 0
    tkba     14.780 / 0

Tuc chung danh ca ngay bang pet SAI. User hoi hai lan: "thay bao dang trong tran hoan doi pet,
nhung qua tran thi cung ko doi" va "party 49 dang di PB, sao thay hien cai nay nhieu the".

GOC: moi loi goi `ensure_pet_role` deu den tu `@_pet_role` (chay truoc/sau moi hoat dong), ma
hoat dong thi xen GIUA cac tran -> gan nhu luon trung luc dang danh. Doc log `vutam`:

    06:55:43  BATTLE ACK g=181 ...            <- tran ket thuc
    06:55:43  doi pet: DANG TRONG TRAN -> hoan
    06:55:46  doi pet: DANG TRONG TRAN -> hoan   <- co in_battle chua kip ha
       (06:55:47 -> 06:55:52 RANH THAT, khong ai goi)
    06:55:53  BATTLE SEND g=182               <- vao tran moi

Vong goi day dac dung luc dang danh, im dung luc ranh - nguoc hoan toan.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src():
    with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
        return fh.read()


def _than(src, dau, thut=4):
    i = src.find(dau)
    if i < 0:
        return ""
    dong = src[i:].split("\n")
    ra = [dong[0]]
    for d in dong[1:]:
        if d.strip() and (len(d) - len(d.lstrip())) <= thut:
            break
        ra.append(d)
    return "\n".join(ra)


class TestGanVaoMocKetTran(unittest.TestCase):
    def setUp(self):
        self.src = _src()

    def test_co_ham_doi_pet_sau_tran(self):
        self.assertIn("def _doi_pet_sau_tran(self):", self.src)

    def test_goi_o_MOI_moc_ket_tran(self):
        """Ba moc: `0x14 sub0700` (WIN), nhanh reset tuong duong, va `0x34`. Thieu moc nao thi
        acc di duong do van ket voi pet sai."""
        self.assertEqual(self.src.count("self._doi_pet_sau_tran()"), 3,
                         "so moc ket tran khong khop voi so cho goi `_heal_after_battle`")

    def test_goi_NGAY_CANH_heal_after_battle(self):
        """Hai viec cung mot moc - tach ra la som muon lech nhau."""
        i = 0
        while True:
            i = self.src.find("self._doi_pet_sau_tran()", i)
            if i < 0:
                break
            truoc = self.src[max(0, i - 300):i]
            self.assertIn("self._heal_after_battle()", truoc)
            i += 10

    def test_KHONG_dat_trong_heal_after_battle(self):
        """`_heal_after_battle` `return` ngay khi quest_mode/boss_mode -> trong PB/quest/boss
        khong bao gio chay, ma do chinh la luc can doi pet nhat (ca party 49)."""
        than = _than(self.src, "    def _heal_after_battle(self):")
        self.assertIn("quest_mode", than, "mat cua return som -> bai hoc nay het y nghia")
        self.assertNotIn("_doi_pet_sau_tran", than)


class TestHamDoiPetSauTran(unittest.TestCase):
    def setUp(self):
        self.than = _than(_src(), "    def _doi_pet_sau_tran(self):")
        self.assertTrue(self.than, "mat ham")

    def test_KHONG_chay_tren_recv_loop(self):
        """`switch_pet` cho server toi 4s - goi thang tren recv-loop la nghen ca luong nhan goi."""
        self.assertIn("threading.Thread", self.than)
        self.assertIn("daemon=True", self.than)

    def test_kiem_lai_in_battle_truoc_khi_doi(self):
        """Giua luc cho grace co the vao tran moi."""
        self.assertIn("not self.state.in_battle", self.than)

    def test_doi_dung_VAI_DANG_CAN_chu_khong_phai_mac_dinh(self):
        """Trong PB thi vai la PB - keo ve vai train giua chung la dung sai pet."""
        self.assertIn("_pet_vai_hien_tai", self.than)
        i = self.than.find("_pet_vai_hien_tai")
        self.assertIn("default_pet_role", self.than[i:i + 200], "mat duong lui khi chua co vai")

    def test_co_CUA_CHONG_CHAY_CHONG(self):
        """Ket tran lien tuc -> de ra ca dong thread cung doi pet."""
        self.assertIn("_doi_pet_sau_tran_active", self.than)


class TestDecoratorNhoVaiDangCan(unittest.TestCase):
    def setUp(self):
        self.than = _than(_src(), "def _pet_role(role):", thut=0)
        self.assertTrue(self.than, "mat decorator `_pet_role`")

    def test_ghi_vai_khi_vao(self):
        self.assertIn("self._pet_vai_hien_tai = role", self.than)

    def test_KHOI_PHUC_vai_cu_khi_ra(self):
        """Hoat dong long nhau (PB trong quest...) - khong khoi phuc thi vai ke thua lung tung."""
        self.assertIn("_truoc", self.than)
        i = self.than.find("finally:")
        self.assertIn("self._pet_vai_hien_tai = _truoc", self.than[i:i + 200])


class TestLogKhongSpam(unittest.TestCase):
    def test_dong_DANG_TRONG_TRAN_o_muc_debug(self):
        """169.507 dong/ngay o muc info = chiem ca file log, va user phai hoi hai lan."""
        than = _than(_src(), "    def switch_pet(self, pid: int, wait: float = 4.0) -> bool:")
        i = than.find("DANG TRONG TRAN -> hoan")
        self.assertGreater(i, 0)
        self.assertIn("log.debug", than[max(0, i - 120):i])

    def test_DOI_PET_thanh_cong_van_o_muc_info(self):
        """Doi that la SU KIEN - phai thay duoc trong log."""
        than = _than(_src(), "    def switch_pet(self, pid: int, wait: float = 4.0) -> bool:")
        i = than.find("DOI PET:")
        self.assertGreater(i, 0)
        self.assertIn("log.info", than[max(0, i - 120):i])


if __name__ == "__main__":
    unittest.main()
