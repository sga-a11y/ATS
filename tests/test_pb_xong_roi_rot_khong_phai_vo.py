"""PHO BAN DA DANH XONG roi moi rot -> KHONG phai "vo", khong lam lai.

Server da tinh luot khi PB xong; danh lai la vo ich, va cai gia phai tra khong chi la thoi gian -
no dua ca party vao lai phong instance trong khi leader dung cho ho relogin.

Ca that 07/09 party 42, ba dong lien nhau:

    10:35:48 [luubmot] (LEADER) === PHO BAN TO DOI LV50 XONG -> roi pho ban ===
    10:35:50 [luu401]  RECONNECT: server rot -> login lai sau 5s (lan 1)
    10:35:58 [luubmot] SERVER NGAT KET NOI: DANG NHAP TRUNG LAP (ma 19)

PB da XONG, nhung dieu kien cu khong xet `ok`:

    broken = ((not ok) or (not c.running) or disc_gen > dg0 or reconnecting)
    if broken: _mark_team_dungeon_broken(st, level)

`not c.running` (leader vua rot) du de danh dau vo -> `o5_need_redo` -> ca party vao LAI phong,
con leader thi dung cho:

    10:39:15..10:40:16 [luubmot] auto phó bản đội: chờ cả party relogin sau PB vỡ (1/5)...
    10:40:39 [luubhai]  go_to_town: DANG TRONG pho ban to doi (map=62012) -> khong teleport
    10:40:39 [luubhai]  (member) reform: CHUA ve duoc Hội Kê (map=62012) -> nghi 10s thu lai

Hai ben cho nhau, 5 phut khong ra.

Van giu `broken` (de thoat instance / relogin) - chi bo phan "dem la mot lan thu that bai" va
"bat lam lai". Rot van la rot, nhung luot thi da an roi.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestNhanhLv50_80_110(unittest.TestCase):
    def test_chi_dem_that_bai_khi_KHONG_ok(self):
        s = _src()
        i = s.rfind("_mark_team_dungeon_broken(st, level)")   # CHO GOI (dinh nghia dung o tren)
        self.assertGreater(i, 0)
        khoi = s[max(0, i - 200):i]
        self.assertIn("if broken and not ok:", khoi,
                      "PB xong roi rot van bi dem la mot lan thu that bai -> lam lai vo ich")

    def test_van_giu_broken_de_thoat_instance(self):
        """Bo luon `broken` thi acc ket trong phong; chi duoc bo phan 'lam lai'."""
        s = _src()
        i = s.find("broken = ((not ok) or (not c.running)")
        self.assertGreater(i, 0, "da bo mat co broken - acc se ket trong instance")
        self.assertIn("_exit_pb_or_reconnect(", s[i:i + 2400])


class TestNhanhLv20(unittest.TestCase):
    def test_ok_thi_KHONG_need_redo(self):
        s = _src()
        i = s.find('st["o5_need_redo"] = True')
        self.assertGreater(i, 0)
        khoi = s[max(0, i - 500):i]
        self.assertIn("(not ok) and (", khoi,
                      "lv20 xong roi rot van bi bat danh lai")

    def test_van_bao_o5_state_done(self):
        """Du xong hay vo, member phai duoc THA ra - khong thi ho dung cho vinh vien."""
        s = _src()
        i = s.find('st["o5_state"] = "done"')
        self.assertGreater(i, 0)
        khoi = s[max(0, i - 700):i + 200]
        self.assertNotIn("if ok:", khoi.split('st["o5_state"] = "done"')[-1])


class TestKhongPhaCaHongThat(unittest.TestCase):
    def test_phong_thieu_nguoi_VAN_lam_lai(self):
        """`_td_incomplete` = roster phong thieu nguoi -> leader HUY truoc khi ton luot, tuc luot
        CHUA mat -> van phai lam lai. Dieu kien moi khong duoc nuot ca truong hop nay."""
        s = _src()
        self.assertIn('getattr(c, "_td_incomplete", False)', s)

    def test_PB_tra_FAIL_van_lam_lai(self):
        s = _src()
        i = s.find("broken = ((not ok) or (not c.running)")
        self.assertIn("(not ok)", s[i:i + 120], "PB fail ma khong lam lai la mat luot oan")


if __name__ == "__main__":
    unittest.main()
