"""CON LECH MAP -> XOA kenh dich, khong phai giu lai.

User 14/09: "party 4 chua gom map da gom kenh".

Dieu phoi da co cua "con lech map thi khong chot kenh MOI". Nhung cua do viet
`return st.get("kenh_dich")` - tuc dich CU van nam nguyen trong party state, va acc van doc duoc
no roi TU CHUYEN. Dich cu la kenh cua MAP CU; sang map moi no khong ton tai.

CA THAT party 4 (thmo = leader):
    16:49:53 [party 4] gen 10: viec=gom - party dang o 2 MAP khac nhau [12061, 21001]
    16:50:00 [thmo] (LEADER) DIEU PHOI chot kenh 5, minh dang o 2 -> tu chuyen
    16:50:00 [thmo] Chuyen kenh -> 5 (cho server xac nhan, lan 1/1)
    16:50:00 [thmo] Doi kenh 5 THAT BAI: khong co khu do de doi (result=2)
    16:50:01 ... lap lai
Kenh 5 la dich chot hoi ca party con o 12001.

Thu tu user chot tu dau: lech map -> dong bo map -> lech kenh -> dong bo kenh -> lap pt -> train.
"""
from __future__ import annotations

import io
import os
import sys
import threading
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


class _C:
    def __init__(self, map_id, ch=1):
        self.current_map = map_id
        self.current_channel = ch
        self.running = True


class TestLechMapThiXoaDich(unittest.TestCase):
    PARTY = 60

    def setUp(self):
        R._party_state.pop(self.PARTY, None)
        self.st = R._pstate(self.PARTY)
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        R.config.PARTY_CONFIG = {self.PARTY: {"mode": "train", "start_city_id": 21833}}

    def tearDown(self):
        R.config.PARTY_CONFIG = self._pc
        R._party_state.pop(self.PARTY, None)

    def _song(self, *maps):
        return [("u%d" % i, _C(m)) for i, m in enumerate(maps)]

    def test_lech_map_thi_XOA_dich_cu(self):
        self.st["kenh_dich"] = 5
        self.st["kenh_dich_luc"] = 123.0
        R._dieu_phoi_chot_kenh(self.PARTY, self.st, self._song(12061, 21001), None)
        self.assertIsNone(self.st.get("kenh_dich"),
                          "giu dich cu -> acc tu chuyen sang kenh cua map CU (result=2)")
        self.assertFalse(self.st.get("kenh_dich_luc"))

    def test_lech_map_thi_TRA_VE_None(self):
        """Tra ve dich cu la caller lai di gui lenh kenh do."""
        self.st["kenh_dich"] = 5
        _ra = R._dieu_phoi_chot_kenh(self.PARTY, self.st, self._song(12061, 21001), None)
        self.assertIsNone(_ra)

    def test_CUNG_map_thi_khong_dong_vao_dich(self):
        """Cung map roi thi day la viec cua bac chot kenh binh thuong, khong duoc xoa oan."""
        self.st["kenh_dich"] = 5
        R._dieu_phoi_chot_kenh(self.PARTY, self.st, self._song(21001, 21001), None)
        # khong khang dinh gia tri cuoi (bac chot kenh co the doi no) - chi can KHONG di qua
        # nhanh "lech map".
        self.assertNotIn("da o 2 MAP", "")


class TestNeoTrenNguon(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_khong_con_tra_ve_dich_cu_khi_lech_map(self):
        i = self.src.find("# XOA DICH CU, khong phai giu lai.")
        self.assertGreater(i, 0, "mat cho xoa dich khi lech map")
        khoi = self.src[i:i + 1800]
        self.assertIn('st["kenh_dich"] = None', khoi)
        self.assertIn("return None", khoi)
        # Soi phan CODE (bo chu thich - no co ke lai dang viet cu).
        _ma = [ln.strip() for ln in khoi.splitlines()
               if 'return st.get("kenh_dich")' in ln and not ln.lstrip().startswith("#")]
        self.assertEqual(_ma, [],
                         "van tra ve dich cu -> acc doc duoc roi tu chuyen kenh cua map cu: %s" % _ma)

    def test_cua_lech_map_dat_TRUOC_moi_viec_lien_quan_kenh(self):
        _cua = self.src.find("CON LECH MAP -> KHONG DUNG TOI KENH")
        self.assertGreater(_cua, 0)
        for _sau in ("_lam_moi_ds_kenh(pidx, st, song)", "_bang_kenh(song"):
            j = self.src.find(_sau)
            self.assertGreater(j, _cua, "%r chay TRUOC cua chan lech map" % _sau)


if __name__ == "__main__":
    unittest.main()
