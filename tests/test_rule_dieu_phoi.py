"""EP LUAT DIEU PHOI (documents/RULE_DIEU_PHOI.md) - phan kiem duoc bang may.

Luat khong co cong chan thi chi la van. File nay bat cac vi pham co the do bang code.
TEST DO O DAY = LUAT BI PHA. Sua CODE, dung sua test.

Cac luat chi soi duoc bang mat (L3 muc tieu do duoc, L4 xu ly tung ma loi, L5 tra no hau qua,
L7 leo thang, L11 dung loai lenh, L12 luong con nghe lenh) -> dung bang "Cam" trong tai lieu.
"""
from __future__ import annotations

import io
import os
import re
import sys
import tokenize
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

NGUON = ("run_party_digioi.py", os.path.join("bot", "client.py"),
         os.path.join("bot", "floor_crawl.py"), os.path.join("bot", "npc40.py"),
         os.path.join("bot", "loandau.py"))


def _doc(p):
    with io.open(os.path.join(ROOT, p), encoding="utf-8") as fh:
        return fh.read()


def _ma_that(src):
    """Cac dong MA THUC SU chay - bo chu thich va chuoi (docstring hay nhac lai bug cu)."""
    bo = set()
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            for ln in range(tok.start[0], tok.end[0] + 1):
                bo.add(ln)
    return [(i, d) for i, d in enumerate(src.splitlines(), 1) if i not in bo]


class TestL0_LuatToiThuong(unittest.TestCase):
    """DU PARTY ROI LAM GI THI LAM. PARTY HONG THI PHAI GOM LAI BANG DUOC.

    Dung tren 13 luat con lai. Ba ca chet that (06/09):
      p5  - 4 member roi doi de doi kenh, leader qua cong len tang 6 MOT MINH, danh 0/3 tran
      p15 - doi tan luc 14:18:57, leader danh mot minh 3 phut/tran suot 4 phut
      p3  - lap "CHO du member san sang (3/4)" 28 lan/1 tieng, moi lan reform deu vo dung
    """

    def test_ve1_khong_qua_cong_khi_thieu_nguoi(self):
        """Qua cong = buoc KHONG QUAY LAI DUOC -> phai co cua kiem du party."""
        fc = _doc(os.path.join("bot", "floor_crawl.py"))
        i = fc.find("client._enter_gate(center[0]")
        self.assertGreater(i, 0)
        truoc = fc[:i]
        self.assertGreater(truoc.rfind("du_party()"), truoc.rfind("for idx in _battle_idx"),
                           "len tang ma khong kiem du party (L0 ve 1)")
        j = fc.find("chua du party -> KHONG len tang mot minh")
        self.assertGreater(j, 0)
        self.assertIn("break", fc[j:j + 200], "thieu nguoi ma van di tiep (L0 ve 1)")

    def test_ve2_thieu_nguoi_thi_MOI_LAI_chu_khong_bo(self):
        src = _doc("run_party_digioi.py")
        i = src.find("def _du_party_2k(")
        self.assertGreater(i, 0, "khong co cho gom lai truoc khi len tang (L0 ve 2)")
        than = src[i:i + 2200]
        self.assertIn("_invite_party_participants(", than, "chua du ma khong moi lai (L0 ve 2)")

    def test_ve2_lenh_lam_TAN_DOI_phai_co_buoc_lap_lai(self):
        """Doi kenh -> server cam khi dang to doi -> tat yeu tan doi -> PHAI lap lai."""
        src = _doc("run_party_digioi.py")
        i = src.find('"-> LAP LAI PARTY", pidx + 1')
        self.assertGreater(i, 0, "doi kenh xong ma khong lap lai doi (L0 ve 2, L5)")
        self.assertIn("joined_member_count(pidx)", src[i - 500:i + 300])

    def test_thieu_nguoi_KHONG_duoc_ket_luan_la_XONG(self):
        """`ket`/`dut` = chua het -> khong duoc bat co thoat. Chi `xong`/`thua`/`het_duong`."""
        src = _doc("run_party_digioi.py")
        i = src.find("def _dieu_phoi_chot_2k_xong(")
        self.assertGreater(i, 0)
        than = src[i:src.find(chr(10) + "def ", i + 10)]
        self.assertIn('kq in ("ket", "dut")', than,
                      "thieu nguoi / dut ket noi ma ket luan la xong (L0, L13)")
        j = than.find('kq in ("ket", "dut")')
        self.assertIn("return", than[j:j + 200])

    def test_trong_thap_2K_KHONG_ra_lenh_doi_kenh(self):
        """"Kenh" trong thap la instanceId cua tang - doi kenh la lenh SAI LOAI, chi lam tan doi.
        Muon cung instance thi phai DI CUNG NHAU QUA CONG (L11)."""
        src = _doc("run_party_digioi.py")
        i = src.find("def _dieu_phoi_chot_kenh(")
        than = src[i:src.find(chr(10) + "def ", i + 10)]
        j = than.find("_tang_gom_2k(pidx, song)")
        self.assertGreater(j, 0, "khong chan lenh doi kenh trong thap 2K (L0, L11)")
        self.assertIn("return None", than[j:j + 300])

    def test_tai_lieu_co_L0(self):
        s = _doc(os.path.join("documents", "RULE_DIEU_PHOI.md"))
        self.assertIn("## L0 — LUẬT TỐI THƯỢNG", s)
        self.assertIn("gom lại BẰNG ĐƯỢC", s)


class TestL1_ChiMotChoDuocQuyet(unittest.TestCase):
    """Mot co QUYET DINH chi duoc `set()` o DUNG MOT cho, va cho do phai la cua dieu phoi."""

    CO_QUYET_DINH = ("event_exit_now",)

    def test_CHI_dieu_phoi_duoc_ra_lenh_doi_kenh(self):
        """Hai co che cung ra lenh doi kenh = khong ai chiu trach nhiem hau qua (TAN DOI).

        Party 5 (06/09, 17:16:26) - leader dang qua cong len tang:
            [thbay] (member) 40NPC: leader chon kenh 2, minh dang o 1 -> BAM SANG kenh leader chon
            [thbay] Doi kenh 2 THAT BAI: DANG TO DOI thi khong doi khu duoc (result=3)
            [thbay] -> roi party roi thu lai
        Ca 4 member roi doi cung luc -> leader leo 12929 -> 12931 -> 12932 -> 12934 MOT MINH.
        """
        src = _doc("run_party_digioi.py")
        self.assertNotIn("BAM SANG kenh leader chon", src,
                         "co che thu hai ra lenh doi kenh -> L1")
        self.assertNotIn("_lan_bam_kenh_leader", src)

    def test_member_chi_soi_kenh_dich_cua_dieu_phoi(self):
        src = _doc("run_party_digioi.py")
        goi = [d for _i, d in _ma_that(src) if "switch_channel(" in d]
        self.assertTrue(goi, "khong con cho nao doi kenh?")
        for d in goi:
            self.assertNotIn('st["channel"]', d,
                             "doi kenh theo co cua vong bat tay cu -> L1: %s" % d.strip())

    def test_co_quyet_dinh_chi_set_o_mot_cho(self):
        src = _doc("run_party_digioi.py")
        for co in self.CO_QUYET_DINH:
            n = src.count('st["%s"].set()' % co)
            self.assertEqual(n, 1, "`%s` duoc set o %d cho -> lai co acc tu quyet (L1)" % (co, n))

    def test_cho_set_nam_trong_ham_cua_dieu_phoi(self):
        src = _doc("run_party_digioi.py")
        for co in self.CO_QUYET_DINH:
            i = src.find('st["%s"].set()' % co)
            self.assertGreater(i, 0)
            truoc = src[:i]
            j = truoc.rfind("\ndef ")
            ten = truoc[j + 5:truoc.find("(", j)]
            self.assertTrue(ten.startswith("_dieu_phoi"),
                            "`%s` set trong `%s()` - phai la ham cua dieu phoi (L1)" % (co, ten))


class TestL2_DocThangCamBaoCao(unittest.TestCase):
    """Ca party trong MOT tien trinh -> doc thang client. Cam co che 'acc bao len'."""

    def test_khong_them_ham_bao_cao_moi(self):
        """`bao_*(st, ...)` = acc ghi vao state cho dieu phoi doc = bao cao (L2)."""
        for f in NGUON:
            for _i, d in _ma_that(_doc(f)):
                m = re.match(r"\s*def (bao_[a-z0-9_]+)\(st\b", d)
                self.assertIsNone(m, "%s: %s -> bat acc bao cao, doc thang client di (L2)"
                                  % (f, d.strip()))

    def test_dieu_phoi_doc_thang_client(self):
        src = _doc("run_party_digioi.py")
        i = src.find("def _doc_ket_qua_doi_kenh(")
        self.assertGreater(i, 0, "khong con cho doc thang ket qua doi kenh (L2)")
        than = src[i:src.find(chr(10) + "def ", i + 10)]
        for truong in ("_chan_switch_result", "_chan_switch_target", "_chan_switch_luc"):
            self.assertIn(truong, than)

    def test_chot_kenh_khong_doc_bang_bao_cao(self):
        src = _doc("run_party_digioi.py")
        i = src.find("def _dieu_phoi_chot_kenh(")
        than = src[i:src.find(chr(10) + "def ", i + 10)]
        self.assertNotIn("channel_map_reports", than)
        self.assertNotIn("bao_kenh", than)


class TestL6_LenhPhaiDinh(unittest.TestCase):
    """Da ra lenh thi giu du lau cho thi hanh xong - dung doi y moi nhip 2 giay."""

    def test_kenh_dich_co_moc_va_han_kien_nhan(self):
        from unittest import mock
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        self.assertGreaterEqual(R.KENH_DICH_KIEN_NHAN_SEC, 30,
                                "han qua ngan -> doi y giua chung, ca party quay dau (L6)")

    def test_giu_dich_cu_khi_chua_qua_han(self):
        src = _doc("run_party_digioi.py")
        i = src.find("def _dieu_phoi_chot_kenh(")
        than = src[i:src.find(chr(10) + "def ", i + 10)]
        self.assertIn("KENH_DICH_KIEN_NHAN_SEC", than)
        self.assertIn("kenh_dich_luc", than)


class TestL8_LenhHongPhaiDongCua(unittest.TestCase):
    def test_co_ham_dong_vong_sync(self):
        src = _doc("run_party_digioi.py")
        i = src.find("def _dong_vong_sync(")
        self.assertGreater(i, 0, "khong co cho dong lenh hong -> co ket set vinh vien (L8)")
        than = src[i:src.find(chr(10) + "def ", i + 10)]
        for k in ('st["channel_ready"].clear()', 'st["channel"] = None',
                  'st["channel_failed"].clear()'):
            self.assertIn(k, than)

    def test_duong_that_bai_cua_sync_deu_dong_cua(self):
        src = _doc("run_party_digioi.py")
        i = src.find("sync kenh/map FAIL %d lan")
        self.assertGreater(i, 0)
        self.assertIn("_dong_vong_sync(st)", src[i - 900:i + 200])


class TestL9_KhongDoLaiChoAccKhac(unittest.TestCase):
    """Thi hanh hong thi ghi nhan roi DI TIEP, khong dung cho dua khac bam nut."""

    def test_doi_kenh_hong_thi_thoat_ngay(self):
        src = _doc("run_party_digioi.py")
        i = src.find("khong doi duoc sang kenh chung")
        self.assertGreater(i, 0)
        sau = src[i:i + 700]
        self.assertNotIn("while", sau, "do lai cho acc khac = L9")
        self.assertIn("return False", sau)

    def test_sai_map_sau_khi_doi_kenh_cung_thoat_ngay(self):
        src = _doc("run_party_digioi.py")
        i = src.find('log.warning("[%s] (member) sang kenh %s roi nhung SAI MAP')
        self.assertGreater(i, 0)
        self.assertIn("return False", src[i:i + 300])


class TestL10_VongThiHanhPhaiCoNhip(unittest.TestCase):
    """Thi hanh xong mot lenh thi NGU mot nhip. `continue` tran = vong nong 8.000 vong/giay."""

    def test_thi_hanh_GOM_xong_co_ngu(self):
        src = _doc("run_party_digioi.py")
        i = src.find("dieu phoi bao GOM (%s) -> thoi moi, gom lai")
        self.assertGreater(i, 0)
        khoi = src[i:i + 2200]
        ngu = khoi.find("time.sleep(KE_HOACH_NHIP)")
        tiep = khoi.find(chr(10) + " " * 24 + "continue")
        self.assertGreater(ngu, 0, "khong ngu -> vong nong, bo doi luon luong dieu phoi (L10)")
        self.assertGreater(tiep, ngu, "ngu phai nam TRUOC continue (L10)")


class TestL13_KhongBietKhacKhongSao(unittest.TestCase):
    """Thieu du lieu phai xu ly nhu 'khong biet', khong duoc mac dinh thanh 'binh thuong'."""

    def test_thua_doc_HP_cua_chinh_minh(self):
        src = _doc("run_party_digioi.py")
        i = src.find("def _party_chet_het(")
        self.assertGreater(i, 0)
        than = src[i:src.find(chr(10) + "def ", i + 10)]
        ma = than[than.find('"""', than.find('"""') + 3):]
        self.assertIn("chet_tran_nay", ma)
        self.assertNotIn("party_defeated", ma,
                         "`allies` rong -> tra False = 'khong thua' = doan bua (L13)")

    def test_client_tu_chot_HP_cua_chinh_no(self):
        src = _doc(os.path.join("bot", "client.py"))
        i = src.find("def _chot_minh_chet(")
        self.assertGreater(i, 0)
        than = src[i:src.find(chr(10) + "    def ", i + 10)]
        self.assertIn('getattr(st, "char", None)', than)

    def test_chot_kenh_khong_quyet_khi_chua_ro(self):
        """Co acc chua ro map/kenh -> KHONG duoc quyet voi."""
        src = _doc("run_party_digioi.py")
        i = src.find("def _dieu_phoi_chot_kenh(")
        than = src[i:src.find(chr(10) + "def ", i + 10)]
        self.assertIn("chua ro het -> khong quyet voi", than)


class TestTaiLieuTonTai(unittest.TestCase):
    def test_co_tai_lieu_luat(self):
        s = _doc(os.path.join("documents", "RULE_DIEU_PHOI.md"))
        for i in range(1, 14):
            self.assertIn("### L%d " % i, s, "thieu luat L%d" % i)

    def test_CLAUDE_md_tro_toi_luat(self):
        self.assertIn("RULE_DIEU_PHOI.md", _doc("CLAUDE.md"),
                      "luat khong duoc tro toi tu CLAUDE.md thi khong ai doc")


if __name__ == "__main__":
    unittest.main()
