"""LEADER KHONG duoc tu giai tan party - chi DIEU PHOI moi duoc phat lenh dong bo.

Luat L1/L2 (`documents/RULE_DIEU_PHOI.md`): chi MOT cho duoc quyet. Truoc day `resync_gen` co BON
cho bump, ba trong so do la LEADER tu quyet, va chi cho cua dieu phoi moi co cooldown + chot
"nguoi khac vua bump thi im". Leader ban thang, khong chot gi.

Ca that 07/09 - hai party chet vi DUNG MOT dong code (`_should_resync_incomplete_digioi_party`,
nguong 20s):

  party 9:
    02:33:26 [lubsau] (LEADER) sync kenh/map OK: 5/5 acc o map 49942
    02:33:30 [lbo006] PARTY: c0edf0a0 vao doi (leader=70edf0a0) -> roster 3 nguoi
    02:33:30 [lbo006] PARTY: loi moi -> DONG Y (lubbay)
    02:33:50 [lubsau] (LEADER) Di Gioi moi 24s chua du party (2/4) -> giai tan + sync lai kenh
    02:33:55..57  lubbay/lubchin/lubtam  Roi/giai tan party cu

  party 11:
    02:10:32 [luusau] PARTY-JOINED: 3 -> 0 (nguoi ghi=ce12fdf4, LEADER) | []
    02:10:32 [luusau] PARTY: loi moi -> DONG Y (luumuoi)      <- member dang vao NGAY luc do
    02:10:33 [luusau] (LEADER) sync kenh/map OK: 5/5 acc o map 49942
    02:10:33 [luusau] (LEADER) moi 1 member theo entity: ... | da join=3 | roster server=3
    02:10:33..34  luuchin/luubay/luutam/luumuoi  leader RE-SYNC party -> roi party
    02:13..02:21  "chua du member (1/4) -> MOI LAI" moi phut   <- 11 PHUT chet

Leader con dem TRE hon roster server ("2/4" trong khi roster da 3 nguoi) nen no dap ca party that
su dang du dan.

Guard phia member cung tung qua hep: ban dau chi bo qua resync khi party DA DU. p9/p11 moi 3-4/5
nen guard truot, ba dua DA VAO bi loi ra theo. Gio chi can `is_joined` - da o trong party thi
lenh resync vo nghia voi minh.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


def _dong_code(s):
    """Cac dong CODE (bo comment/docstring tho) - de khong bat nham chu thich ke ca bug."""
    ra = []
    for d in s.splitlines():
        t = d.strip()
        if not t or t.startswith("#"):
            continue
        ra.append(d)
    return ra


class TestChiDieuPhoiBumpResync(unittest.TestCase):
    def test_chi_MOT_cho_bump_resync_gen(self):
        bump = [d.strip() for d in _dong_code(_src()) if "resync_gen" in d and "+= 1" in d]
        self.assertEqual(len(bump), 1,
                         "co %d cho bump resync_gen -> nhieu cho cung ra lenh (L1): %s"
                         % (len(bump), bump))

    def test_cho_do_nam_trong_dieu_phoi(self):
        s = _src()
        i = s.find('st["resync_gen"] += 1')
        self.assertGreater(i, 0)
        khoi = s[max(0, i - 1500):i + 400]
        self.assertIn("DIEU PHOI", khoi, "cho bump duy nhat phai la cua dieu phoi")

    def test_leader_khong_con_tu_giai_tan_khi_moi_chua_du(self):
        """`leave_party()` + `reset_party_joined()` ngay trong vong MOI party = tu dap cai dang gom."""
        s = _src()
        i = s.find("while not _dg_solo_bail and joined_member_count(pidx) < st[\"n_members\"]:")
        self.assertGreater(i, 0)
        j = s.find("(LEADER) DU PARTY", i)
        self.assertGreater(j, i)
        vong = "\n".join(_dong_code(s[i:j]))
        self.assertNotIn("reset_party_joined(pidx)", vong,
                         "leader van tu xoa danh sach da-join giua vong moi party")


class TestMemberDaVaoThiKhongRoi(unittest.TestCase):
    def test_guard_chi_can_is_joined(self):
        s = _src()
        i = s.find("leader RE-SYNC party -> roi party + sync kenh lai")
        self.assertGreater(i, 0)
        khoi = s[max(0, i - 1400):i]
        self.assertIn("if is_joined(pidx, c.self_entity):", khoi,
                      "guard phai la 'da vao party thi bo qua', khong kem dieu kien du nguoi")

    def test_khong_con_dieu_kien_du_nguoi(self):
        """Vet `joined_member_count(...) >= st['n_members']` trong guard = ca p9/p11 quay lai."""
        s = _src()
        i = s.find("leader RE-SYNC party -> roi party + sync kenh lai")
        khoi = s[max(0, i - 1400):i]
        self.assertNotIn(">= st[\"n_members\"]", khoi,
                         "guard van doi party DU moi bo qua -> party 3-4/5 lai bi loi ra")


class TestKhongSpamLog(unittest.TestCase):
    def test_log_moi_chua_du_co_chan_nhip(self):
        """Bo nhanh giai tan thi vong quay rat nhanh - log moi vong la ngap party.log."""
        s = _src()
        i = s.find("if _should_resync_incomplete_digioi_party(")   # CHO GOI, khong phai dinh nghia
        self.assertGreater(i, 0)
        self.assertIn("_resync_log_luc", s[i:i + 700])


if __name__ == "__main__":
    unittest.main()
