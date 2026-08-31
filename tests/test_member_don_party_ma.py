"""Member ket ngoai party phai DON PARTY MA truoc khi retry.

Server KHONG gui loi moi cho nguoi DANG O PARTY. Ma bot chi gui goi roi party khi TRANG THAI
LOCAL noi minh dang o party (`in_party` trong do_channel_sync doc party_members/party_leader).
Local rong + server con giu party cu = KET VINH VIEN: leader moi hoai, member khong bao gio
nhan duoc goi moi nao.

Party 15 (27/08): goi roster CUOI CUNG luc 08:48:44; sau do 35 phut leader gui hang tram luot
moi, 2/4 member (trubay, trumuoi) khong nhan duoc mot goi moi nao, 2 con lai accept ma party
van khong hinh thanh (`da join=2 | roster server=0 nguoi`).
"""
from __future__ import annotations

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class TestDonPartyMa(unittest.TestCase):
    def setUp(self):
        self.src = _doc("run_party_digioi.py")
        i = self.src.find("elif not is_joined(pidx, c.self_entity):")
        self.assertGreater(i, 0, "khong tim thay nhanh member retry vao party")
        self.khoi = self.src[i:i + 5600]

    def test_co_goi_leave_party_khi_retry(self):
        than = re.sub(r"#.*", "", self.khoi)      # bo chu thich - bay hay gap trong repo nay
        self.assertIn("c.leave_party(", than,
                      "member khong bao gio don party ma -> server khong gui loi moi toi")

    def test_gui_ID_DOI_TRUONG_chu_khong_phai_cua_minh(self):
        """`C:013-004` mang ID doi truong. Gui ID cua minh = server bo qua = khong go duoc gi.

        Member ket ngoai party thi chua nhan roster nao -> `c.party_leader` rong -> phai lay
        entity live cua acc leader trong tien trinh nay.
        """
        than = re.sub(r"#.*", "", self.khoi)
        self.assertIn("leader_entity=", than, "van gui ID cua minh -> party ma khong go duoc")
        self.assertIn("party_accounts(pidx)", than, "khong tim entity cua acc leader")

    def test_CHI_don_khi_local_khong_thay_roster(self):
        """Dang o party THAT (co roster) ma goi leave la tu pha party dang chay.

        Ngoai le duy nhat: roster SERVER (`_doi_truong_dang_ket`) noi minh dang o party cua NGUOI
        KHAC - do la su that tu server, manh hon trang thai local.
        """
        than = re.sub(r"#.*", "", self.khoi)
        i_guard = than.find('_ket_party_la or not getattr(c, "party_members", None):')
        self.assertGreater(i_guard, 0, "mat cua chan roster local")
        i_leave = than.find("c.leave_party(")
        self.assertLess(i_guard, i_leave, "goi leave_party NGOAI cua chan roster")

    def test_go_luon_dau_da_join(self):
        than = re.sub(r"#.*", "", self.khoi)
        self.assertIn("unmark_joined(pidx, c.self_entity)", than)

    def test_loi_khi_don_KHONG_chan_retry(self):
        """Don party ma chi la don dep - loi o day khong duoc lam member bo luon buoc doi kenh."""
        than = re.sub(r"#.*", "", self.khoi)
        # Neo theo CHINH loi goi leave_party (khoi nay con nhieu try/except khac), khong lay
        # "try:" dau tien cua ca doan.
        i_leave = than.find("c.leave_party(")
        self.assertGreater(i_leave, 0)
        i_try = than.rfind("try:", 0, i_leave)
        i_except = than.find("except Exception as e:", i_leave)
        self.assertTrue(0 <= i_try < i_leave < i_except, "loi khi don party ma khong duoc bao")


class TestLogChanDoan(unittest.TestCase):
    """Party 15 ton 2 vong dieu tra vi log khong noi leader dang dem duoc may nguoi."""

    def test_vong_moi_in_so_dem_va_roster(self):
        s = _doc("bot", "client.py")
        i = s.find("moi %d member theo entity")
        self.assertGreater(i, 0)
        khoi = s[i:i + 500]
        self.assertIn("da join=%d", khoi)
        self.assertIn("roster server=%d", khoi)


if __name__ == "__main__":
    unittest.main()
