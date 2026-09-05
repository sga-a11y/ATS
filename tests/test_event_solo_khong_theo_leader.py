"""EVENT SOLO thi LEADER khong lien quan gi - bot moi la nguoi quyet dinh.

Rule user chot 05/09: "bo cai leader quyet dinh di, bot moi la nguoi quyet dinh" va
"da danh solo thi lien quan gi den leader".

BUG THAT 05/09 22:21 (party 11, loan dau THU 7 - event SOLO):
    [luusau]  (LEADER) LOAN DAU: danh xong 1 tran ... -> ra khoi map + thoat game
    [luutam]  (member) CHU PARTY da thoat -> member thoat theo
    [luutam]  Loan dau: tran khong thay ket thuc -> dung
    [luumuoi] (member) pos=(1630, 430) map=54901 combat=True     <- VAN DANG DANH
3 acc bi keo thoat giua tran, mat luot. Loan dau KHONG lap party, KHONG sync kenh - "leader"
chi la vai tro ghi trong config.
"""
from __future__ import annotations

import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestKhongTheoLeaderKhiSolo(unittest.TestCase):
    def _dieu_kien(self):
        """Neo tu CHINH dong log cua nhanh do - `leader_gone` con duoc doc o 2 cho khac
        (cho leader keo route, va ngung retry vao party) khong lien quan."""
        s = _src()
        i = s.find('"[%s] (member) CHU PARTY da thoat -> member thoat theo"')
        self.assertGreater(i, 0, "khong con nhanh 'chu party thoat -> member thoat theo'")
        j = s.rfind('if ((not is_leader)', 0, i)
        self.assertGreater(j, 0)
        return s[j:s.find(":\n", j) + 1]

    def test_loai_tru_MOI_che_do_solo(self):
        dk = self._dieu_kien()
        for co in ("digioi_solo", "event_stand_mode", "event_solo_kind"):
            self.assertIn("not %s" % co, dk, "quen loai tru %s -> acc solo bi keo thoat oan" % co)

    def test_event_solo_kind_co_truoc_khi_dung(self):
        """Dung bien chua gan la NameError giua vong keepalive -> chet acc."""
        s = _src()
        self.assertLess(
            s.find("event_solo_kind = "),
            s.find('"[%s] (member) CHU PARTY da thoat -> member thoat theo"'),
            "dung `event_solo_kind` TRUOC khi gan -> NameError giua vong keepalive")

    def test_hai_nhanh_theo_leader_KIA_van_loai_tru_event_solo(self):
        """`resync_gen` va `disc_gen` cung keo member theo leader - phai khong dinh event solo."""
        s = _src()
        for moc in ('st["resync_gen"] > resync_gen_handled', 'st["disc_gen"] > disc_gen_handled'):
            i = s.find(moc)
            self.assertGreater(i, 0, moc)
            khoi = s[s.rfind("if ", 0, i):i]
            self.assertTrue("event_party_mode" in khoi,
                            "%s khong phan biet event party vs event solo" % moc)


class TestLoanDauVanLaSOLO(unittest.TestCase):
    def test_chaos_vs_nam_trong_danh_sach_event_solo(self):
        s = _src()
        i = s.find("_SOLO_BATTLE_EVENTS")
        self.assertGreater(i, 0)
        self.assertIn("chaos_vs", s[i:i + 120])

    def test_loan_dau_KHONG_phai_event_party(self):
        """`_is_party_event` bat la se lap party + sync kenh - sai han thiet ke loan dau."""
        s = _src()
        i = s.find("def _is_party_event(")
        than = s[i:s.find("\ndef ", i + 10)]
        self.assertNotIn("chaos_vs", than)


if __name__ == "__main__":
    unittest.main()
