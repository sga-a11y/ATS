"""LEADER SAI MAP cung KHONG co xu ly rieng - ra vong chinh nghe lenh dieu phoi.

User 13/09: "Party 48 ko thay lap pt".

Nhanh MEMBER da bi xoa vong tu-cho tu 11/09, nhung nhanh LEADER van con mot vong y het:

    while c.running and not _stopped():
        _resync_ck(st, username)
        _do_reform(to_spot=False)
        ...
        time.sleep(5)

Acc TU CHON buoc vao vong do, va trong do no DIEC voi moi lenh cap party.

CA THAT (party 48, 13/09):

    10:41:11 [party 48] gen 5: viec=moi - cung map/kenh nhung DOI chua du (dt901=0 ... dt905=0)
    10:41:11 [party 48] DIEU PHOI: ... -> LAP LAI PARTY
    10:42:05 [dt901]    Da ve thanh 18021
    10:42:05 [dt901]    KHONG o party nao (roster server + local deu rong) -> KHONG gui 013-004
    10:42:10 [dt901]    KHONG o party nao ...          <- 5 giay MOT DONG
    ...      [dt901]    ... khong dut cho den het log (10:47:51)

`dt901` la LEADER. Cu 5 giay `_do_reform` mot lan; moi lan teleport lai `leave_party()` -> chinh
la dong log tren. No khong bao gio chay toi doan GUI LOI MOI, nen dieu phoi ra lenh "lap lai
party" deu dan ma khong ai thi hanh -> user thay "ko lap pt".

Truoc do party 48 dung o THIEU NGUOI (1/4) tu 07:56 den 10:30 (hon hai tieng ruoi), watcher ep
dong bo hang chuc lan hoan toan vo ich - cung mot nguyen nhan.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _ma(s):
    s = re.sub(r'"""[\s\S]*?"""', "", s)
    return re.sub(r"#.*", "", s)


class _Nen(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def _khoi_leader_sai_map(self):
        """Tu dong log '(LEADER) SAI MAP ... khong dung duoc duong' den het nhanh leader."""
        i = self.src.find("(LEADER) SAI MAP (o %s, can %s) va khong dung duoc duong")
        self.assertGreater(i, 0, "mat nhanh leader sai map")
        j = self.src.find('st["leader_ok"].set()', i)
        self.assertGreater(j, i, "mat moc ket thuc nhanh leader")
        return _ma(self.src[i:j])


class TestLeaderKhongTuLapVong(_Nen):
    def test_khong_con_vong_tu_reform(self):
        khoi = self._khoi_leader_sai_map()
        self.assertNotIn("while c.running", khoi,
                         "leader lai tu dung mot vong rieng -> diec voi lenh dieu phoi")

    def test_khong_con_tu_goi_reform(self):
        khoi = self._khoi_leader_sai_map()
        self.assertNotIn("_do_reform", khoi, "leader lai tu quyet di gom")

    def test_khong_con_ngu_5_giay(self):
        """`time.sleep(5)` trong nhanh nay = nhip cua chinh vong tu-cho."""
        khoi = self._khoi_leader_sai_map()
        self.assertNotIn("time.sleep(5)", khoi)

    def test_ra_vong_chinh_de_nghe_lenh(self):
        i = self.src.find("(LEADER) SAI MAP (o %s, can %s) -> KHONG tu xu ly")
        self.assertGreater(i, 0, "leader sai map khong con ra vong chinh")
        self.assertIn("nghe lenh dieu phoi", self.src[i:i + 400])


class TestLeaderKhongTuThoat(_Nen):
    def test_sai_map_khong_lam_leader_tu_quit(self):
        khoi = self._khoi_leader_sai_map()
        self.assertNotIn("_quit()", khoi, "sai map khong phai ly do de acc tu tat")

    def test_khong_set_leader_bad(self):
        """Leader van song - danh dau hong la giet het member."""
        khoi = self._khoi_leader_sai_map()
        self.assertNotIn('st["leader_bad"].set()', khoi)

    def test_van_set_leader_ok_de_member_khong_treo(self):
        i = self.src.find("(LEADER) SAI MAP (o %s, can %s) -> KHONG tu xu ly")
        self.assertIn('st["leader_ok"].set()', self.src[i:i + 900],
                      "khong set leader_ok -> member cho leader vo han")

    def test_khong_con_ham_daily_then_quit(self):
        """Ham do chi ton tai de nhanh sai map tu thoat - khong con ai goi."""
        self.assertNotIn("_daily_then_quit", _ma(self.src))


class TestHaiNhanhXuLyGiongNhau(_Nen):
    """Leader va member phai cung mot cach xu su: sai map = TRANG THAI, dieu phoi lo."""

    def test_ca_hai_deu_ra_vong_chinh(self):
        for _vai in ("(LEADER)", "(member)"):
            i = self.src.find("%s SAI MAP (o %%s, can %%s) -> KHONG tu xu ly" % _vai)
            self.assertGreater(i, 0, "%s khong ra vong chinh" % _vai)

    def test_ca_hai_deu_khong_tat_party(self):
        for _vai in ("(LEADER)", "(member)"):
            i = self.src.find("%s SAI MAP (o %%s, can %%s) va khong dung duoc duong" % _vai)
            self.assertGreater(i, 0)
            self.assertIn("KHONG tat party", self.src[i:i + 400])


if __name__ == "__main__":
    unittest.main()
