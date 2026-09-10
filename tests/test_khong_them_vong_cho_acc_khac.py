"""CAM THEM VONG CHO ACC KHAC. Test nay ton tai vi TOI - khong phai vi ai khac.

User 10/09: "den bao gio m moi het code ngu day, viet luat ma deo them lam".

Dung. `documents/RULE_DIEU_PHOI.md` co 28 luat, L1/L2 noi ro "khong acc nao cho acc khac bao cao".
Chinh trong ngay viet nhung luat do, toi them `_cho_leader_keo()` - mot vong cho co cua leader -
va no giet party 1 luc 22:50:

    22:50:40 [xGAx]   qua cong idx=1 -> map 21521       <- leader VAN DANG KEO
    22:50:52 [chihao] THOI CHO leader keo (route_done) sau 120s
    22:50:57 [chihao] pre-route: tele trung gian ve thanh 12001 truoc
    22:50:57 [chihao] Teleport: dang o to doi -> ROI DOI truoc      <- party TAN giua duong

Doc khong chan duoc gi - doc chi la chu. Test nay chan.

QUY TAC: mot vong `while` doc TRANG THAI DO ACC KHAC GHI (`st[...]` cua party, so member da join,
co cua leader) thi PHAI co it nhat mot trong cac loi ra doc lap voi acc kia:

    * `_nghe_lenh_kenh()`  - nghe duoc lenh dieu phoi ngay trong vong
    * `_ke_hoach(st)`      - doc lenh dieu phoi roi tu quyet di tiep hay thoi
    * "khong con chay"     - thoat khi acc kia da tat

HOAC phai KHAI BAO LY DO bang mot dong `# CHO-HOP-LE:` ngay tren vong. Test khong cam mu - co
nhung vong cho that su hop le (leader chu dong moi lai moi vong; rang buoc THU TU cua game; luong
quan sat chi doc). Nhung phai VIET RA tai sao: buoc nguoi them phai dung lai nghi, thay vi them
mot vong cho nua roi di tiep - dung cai toi da lam voi `_cho_leader_keo`.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Vong doc mot trong cac thu nay = doc trang thai do ACC KHAC ghi.
DOC_ACC_KHAC = (
    "joined_member_count(",      # so member da join - do member khac ghi
    "cmd_leader_xong_gen",       # co leader bat
    "route_party_ready",         # co leader bat
    "route_done",                # co leader bat
    'st["reconnecting"]',        # acc khac dang login lai
    "channel_ready",             # picker bat
)

# Loi ra hop le: khong phu thuoc acc kia.
LOI_RA = (
    "_nghe_lenh_kenh()",
    "_ke_hoach(st)",
    "khong con chay",
    "_het_kien_nhan()",          # han kien nhan rieng cua vong sync kenh
    "_sync_gen_moved()",         # dieu phoi da chuyen huong
)


def _ma_khong_ghi_chu(s):
    """Bo docstring + comment nhung GIU NGUYEN SO DONG (thay bang dong trong).

    Xoa han docstring thi so dong bao trong loi test lech voi file that - nguoi doc phai di do
    lai, ma do sai la sua nham cho.
    """
    s = re.sub(r'"""[\s\S]*?"""',
               lambda m: "\n" * m.group(0).count("\n"), s)
    return re.sub(r"#.*", "", s)


def _khai_bao(src, so_dong, nhin_len=6):
    """Vai dong NGAY TREN vong - noi phai co `# CHO-HOP-LE:` neu vong do la ngoai le."""
    dong = src.split(chr(10))
    i = max(0, so_dong - 1 - nhin_len)
    return chr(10).join(dong[i:so_dong - 1])


def _cac_vong_cho(src):
    """[(so_dong, dong_while, than_vong)] - chi vong CO NGU (cho), bo vong tinh toan."""
    dong = _ma_khong_ghi_chu(src).split("\n")
    ra = []
    for i, d in enumerate(dong):
        if not re.match(r"\s*while ", d):
            continue
        than = "\n".join(dong[i + 1:i + 30])
        if "time.sleep" in than or ".wait(" in than:
            ra.append((i + 1, d.strip(), than))
    return ra


class TestKhongCoVongChoAccKhacMaDiec(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_moi_vong_cho_acc_khac_deu_nghe_duoc_lenh(self):
        xau = []
        for so, dau, than in _cac_vong_cho(self.src):
            _ca = dau + "\n" + than
            if not any(k in _ca for k in DOC_ACC_KHAC):
                continue                       # khong cho acc khac -> khong thuoc dien nay
            if any(k in _ca for k in LOI_RA):
                continue                       # co loi ra doc lap -> hop le
            if "CHO-HOP-LE" in _khai_bao(self.src, so):
                continue                       # da khai bao ly do ngay tren vong
            xau.append("dong %d: %s" % (so, dau[:80]))
        self.assertEqual(xau, [], "vong cho acc khac ma DIEC voi lenh dieu phoi:\n  " +
                                  "\n  ".join(xau))

    def test_ham_cho_leader_keo_KHONG_duoc_quay_lai(self):
        """Ham do da bi xoa 10/09. Them lai la lap lai dung ca party 1 / party 50."""
        self.assertNotIn("_cho_leader_keo", self.src)
        self.assertNotIn("CHO_LEADER_KEO_SEC", self.src)

    def test_member_khong_doc_co_route_cua_leader(self):
        """`route_party_ready` / `route_done` chi con leader GHI, khong ai NAM CHO."""
        ma = _ma_khong_ghi_chu(self.src)
        for _co in ("route_party_ready", "route_done"):
            for m in re.finditer(r'while [^\n]*%s' % _co, ma):
                self.fail("con vong cho co '%s': %s" % (_co, m.group(0)[:80]))


class TestDanhSachVongChoKhongPhinhTo(unittest.TestCase):
    """Chot so vong cho hien tai. Them vong moi -> test do -> phai doc lai luat truoc khi them.

    Khong cam tuyet doi (vai vong la vong chinh / cho server tra loi trong vai giay), nhung moi
    lan con so tang la mot lan phai tra loi: vong nay CO PHAI acc dang cho acc khac khong.
    """

    TRAN = 28        # do 10/09 sau khi xoa `_cho_leader_keo` (them vong moi -> doc L1/L2 truoc)

    def test_so_vong_cho_khong_vuot_tran(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        n = len(_cac_vong_cho(src))
        self.assertLessEqual(
            n, self.TRAN,
            "them %d vong cho moi. Doc documents/RULE_DIEU_PHOI.md muc L1/L2 truoc khi them: acc "
            "KHONG cho acc khac. Neu that su can, cap nhat TRAN va giai thich trong commit."
            % (n - self.TRAN))


if __name__ == "__main__":
    unittest.main()
