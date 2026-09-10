"""DIEU PHOI TU DOC gio Di Gioi cua tung acc - acc KHONG khai bao (L2).

Ban cu: acc tu ket luan "minh xong DG" roi ghi co `c._dg_da_xong`, dieu phoi doc lai ket luan do.
Co nam tren client KHONG lam no thoi la bao cao - chi khac cho cat. Acc ket luan sai la ca party
tin theo va dung cho no.

Ca that 09/09 party 2 (user: "p2 co dua deo them vao Di gioi kia" -> "xong cai dau lon, vua qua
ngay moi, dua nao cung co 2h Di gioi" -> "nho la bot dieu phoi phai lam va kiem tra cac acc, deo
phai cac tu lam roi bao cao nhe"):

    00:54:40 [haabo] Boss QD: khong vao duoc tran -> RELOGIN ngay
    00:54:41 [haabo] Server dong ket noi
    00:54:57 [haabo] (member) KHONG vao lai duoc DG (map=23822) -> coi la HET GIO DG
    00:55:57 [haabo] DG+Train: xong DG, DUNG YEN cho party (1/5 acc xong)

16 giay sau khi mat ket noi da tu ghi "xong DG". Ca ngay no CHUA VAO DG lan nao (0 dong "da VAO DI
GIOI") va vua sang ngay moi nen con nguyen 120 phut.

Nguon su that (doc thang tu client):
  - `S:097-001` ma 2 <時間已滿>            -> het gio
  - dong ho `S:085-001` id 0x1b            -> con >= 1 phut la con gio
  - chua co dong ho (`_last_digioi_ts`=0)  -> CHUA BIET, phai cho (khong duoc suy thanh het gio)

`S:085-001` do SERVER TU DAY: crack client khong co goi xin (`protocolTable[85]` chi co ba nhanh
S:085-001/002/003), va client ghi "跨日時會更新資料" = qua ngay server gui lai.
"""
from __future__ import annotations

import io
import os
import sys
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


class _C:
    """Client gia - chi cac truong `_acc_het_gio_dg` doc."""

    def __init__(self, used=0, co_dong_ho=True, running=True, ma_vao=None, trong_dg=False):
        self.running = running
        self.digioi_minutes = used
        self._last_digioi_ts = time.time() if co_dong_ho else 0.0
        self._dg_enter_result = ma_vao
        self._trong_dg = trong_dg

    def in_di_gioi(self):
        return self._trong_dg

    def digioi_minutes_live(self):
        return float(self.digioi_minutes)


class TestAccHetGioDG(unittest.TestCase):
    def test_con_gio_thi_False(self):
        self.assertIs(R._acc_het_gio_dg(_C(used=0)), False)
        self.assertIs(R._acc_het_gio_dg(_C(used=60)), False)

    def test_het_gio_thi_True(self):
        self.assertIs(R._acc_het_gio_dg(_C(used=R.DIGIOI_LIMIT)), True)

    def test_server_bao_ma_2_thi_True(self):
        """`S:097-001` ma 2 <時間已滿> - server noi thang, khong can dong ho."""
        self.assertIs(R._acc_het_gio_dg(_C(used=0, co_dong_ho=False, ma_vao=2)), True)

    def test_CHUA_CO_DONG_HO_thi_None_chu_KHONG_phai_het_gio(self):
        """Vua login lai / server chua day `S:085-001` -> CHUA BIET.

        Day la cho sinh ra ca `haabo`: chua biet ma ket luan het gio thi acc mat ca luot DG va ca
        party dung cho no."""
        self.assertIsNone(R._acc_het_gio_dg(_C(used=0, co_dong_ho=False)))

    def test_acc_DIS_thi_None(self):
        """Mat ket noi thi khong ket luan gi - `enter_di_gioi_safe` truot la vi duong truyen."""
        self.assertIsNone(R._acc_het_gio_dg(_C(used=0, running=False)))
        self.assertIsNone(R._acc_het_gio_dg(None))

    def test_ma_1_KHONG_phai_het_gio(self):
        """Ma 1 = <等級不足>, khong lien quan gio."""
        self.assertIs(R._acc_het_gio_dg(_C(used=0, ma_vao=1)), False)


class TestKhongConCoAccTuKhai(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_khong_con_GAN_co_dg_da_xong(self):
        """Con mot cho gan la con duong acc tu khai."""
        for cam in ("_dg_da_xong = True", "_dg_da_xong = False"):
            self.assertNotIn(cam, self.src, cam)

    def test_khong_con_DOC_co_dg_da_xong(self):
        self.assertNotIn('getattr(account_clients.get(u), "_dg_da_xong"', self.src)

    def test_cho_dem_acc_xong_DG_dung_ham_dieu_phoi(self):
        i = self.src.find("done = {u for u in users")
        self.assertGreater(i, 0)
        self.assertIn("_acc_het_gio_dg(", self.src[i:i + 200])

    def test_CHUA_BIET_khong_duoc_tinh_la_xong(self):
        """`is True` chu khong phai truthy: `None` (chua biet) phai KHAC `True` (het gio)."""
        i = self.src.find("done = {u for u in users")
        self.assertIn("is True", self.src[i:i + 200],
                      "dung truthy thi None cung thanh 'xong' -> ca party bo di train oan")

    def test_gather_giveup_cung_doc_thang(self):
        i = self.src.find("def _dg_gather_giveup():")
        self.assertGreater(i, 0)
        khoi = self.src[i:i + 1200]
        self.assertIn("_acc_het_gio_dg(", khoi)
        self.assertIn("is True", khoi)


class TestReloginBoDongHoCu(unittest.TestCase):
    """RELOGIN dung LAI cung object -> khong bo moc thi bot xai so phut cua PHIEN TRUOC, va
    `digioi_minutes_live()` con cong thoi gian troi LEN CHINH so cu do."""

    def test_relogin_xoa_moc_dong_ho(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("def relogin(self):")
        self.assertGreater(i, 0)
        j = s.find("def ", i + 10)
        khoi = s[i:j]
        self.assertIn("self._last_digioi_ts = 0.0", khoi,
                      "khong bo moc dong ho DG khi login lai -> xai so phut phien truoc")

    def test_van_GIU_digioi_minutes_lam_tham_khao(self):
        """Chi xoa MOC, khong xoa so - cho nao can van co so cu de doi chieu."""
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("def relogin(self):")
        j = s.find("def ", i + 10)
        self.assertNotIn("self.digioi_minutes = 0", s[i:j])


if __name__ == "__main__":
    unittest.main()
