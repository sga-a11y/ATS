"""RA SOAT: acc khong duoc TU HANH DONG lam hong doi khi khong co lenh dieu phoi.

User 14/09, sau ba tuan sua long vong: "logic t mong muon: lech map thi dong bo map / lech kenh thi
dong bo kenh / cung kenh cung map thi lap pt / du pt thi chay di train. Cai logic nay co phuc tap
ko ma may code 3 tuan deo xong" -> "ra soat het toan bo cho tao".

Bon buoc do KHONG phuc tap, va chung DA DUNG trong `_dieu_phoi_quyet`. Loi nam o hai tang khac:

  (1) DAU VAO SAI  - logic dung nhung doc phai con so sai
        map train    : doc o `train_map_dich` (dien muon) thay vi `auto_train`
        doi du chua  : doc ban sao ngheo nhat cua member thay vi roster LEADER
        dang o PB    : doc dong ho `now + 20 phut` thay vi `current_map`
        level party  : cho pet xac nhan moi dam chot bai train

  (2) DAU RA KHONG AI BUOC PHAI NGHE - dieu phoi ra lenh dung, acc van tu lam
        leader MOI PARTY LA MAC DINH, chi dung khi thay dung chu `gom`
        acc TU DI BOSS QD -> `leave_party()` bat ke dieu phoi dang ra lenh gi
        mot dua ROT -> leader TU GIAI TAN ca party dang lanh

Do tren log that 14/09 (3.5 gio, 78 party):
    549  lenh "LAP LAI PARTY" phat ra, trong do 130 (24%) luc LEADER DA THAY DU ROSTER
    759  lan leader `Roi/giai tan party cu`
    104  lan acc tu roi party di boss Quan Doan
     94  lan mot dua rot -> leader giai tan ca party
   1903  lan "MAT PARTY giua chung" (he qua cua nhung cai tren)

File nay neo tang (2): moi duong acc tu hanh dong deu phai co lenh hoac ly do bat buoc.
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


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestBossQDPhaiCoLenh(unittest.TestCase):
    """Boss Quan Doan la instance SOLO -> bat buoc roi party. Nhung KHI NAO di thi phai theo lenh."""

    def setUp(self):
        self.src = _src()

    def test_chi_di_khi_dieu_phoi_bao_LAM(self):
        i = self.src.find("boss QD den luot nhung dieu phoi dang ra lenh")
        self.assertGreater(i, 0, "acc van tu di boss QD bat ke dieu phoi ra lenh gi")
        truoc = self.src[max(0, i - 600):i]
        self.assertIn("_viec_bq not in (None, VIEC_LAM)", truoc)

    def test_cua_dat_TRUOC_khi_roi_party(self):
        _cua = self.src.find("_viec_bq = (_ke_hoach(st) or {}).get(\"viec\")")
        _roi = self.src.find("# Boss QD la instance SOLO -> roi party truoc khi vao.")
        self.assertGreater(_cua, 0, "mat cua chan boss QD")
        self.assertGreater(_roi, 0, "mat cho roi party cua boss QD")
        self.assertLess(_cua, _roi, "cua chan dat SAU khi da roi party -> vo nghia")

    def test_khong_spam_log_khi_hoan(self):
        self.assertIn("boss_qd_cho_log", self.src)


class TestDieuPhoiKHONG_CHO_ai(unittest.TestCase):
    """DIEU PHOI KHONG DUOC CHO AI - chuyen "dang viec vat thi chua vao party" DA giai o tang acc.

    User 14/09: "code da co han cho nhan loi moi nhung chua chap nhan, phai cho xong viec vat roi
    moi nhan loi moi vao pt roi, the ma may con dinh bo di".

    Co che co san trong `bot/client.py::_on_party_invite`:
        loi moi tu acc CUNG PARTY  -> ACCEPT NGAY du dang viec vat (L0)
        con lai                    -> `_pending_party_invites[entity]` = GIU lai, xong viec moi nhan
    Tuc leader cu moi, khong ai bi keo di giua chung, ma party van hinh thanh.

    T da them mot bac chan o dieu phoi lam lai chinh viec do -> viec vat thi acc nao cung lam lien
    tuc nen LUC NAO cung co nguoi ban -> khong bao gio ra lenh -> ca party dung o thanh (204 lan,
    14/09: "bon no lai ket o thanh deo di dau kia"). Da go.
    """

    def setUp(self):
        self.src = _src()

    def test_co_che_GIU_LOI_MOI_van_con(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            kc = fh.read()
        self.assertIn("self._pending_party_invites[bytes(entity)] = time.time()", kc,
                      "mat co che giu loi moi -> acc dang viec vat bi keo di giua chung")

    def test_KHONG_con_duong_accept_ngay_bo_do_viec_vat(self):
        """User 14/09: "nhan loi moi ma chap nhan ngay thi lai hong viec vat"."""
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            kc = fh.read()
        self.assertNotIn("ACCEPT NGAY du dang viec vat", kc,
                         "lai keo acc dang viec vat vao party -> hong viec vat")

    def test_cho_NHA_loi_moi_nam_o_cho_KHONG_THE_QUEN(self):
        """`account_task.__exit__` chay ca khi viec vat nem loi / bi abort."""
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            kc = fh.read()
        i = kc.find("    def __exit__(self, et, ev, tb):")
        self.assertGreater(i, 0)
        khoi = kc[i:i + 1600]
        self.assertIn("set_party_invite_ready(True)", khoi,
                      "xong viec vat khong nha loi moi da giu -> ket vinh vien")

    def test_bat_co_chi_khi_acc_DANG_RANH(self):
        """Go co ket False, nhung khong duoc mo khi acc dang GIUA mot viec vat."""
        self.assertIn("and not c.dang_lam_viec_vat()", self.src)
        self.assertEqual(self.src.count("c.dang_lam_viec_vat()"), 2,
                         "con duong ep bat co vo dieu kien")

    def test_dang_lam_viec_vat_doc_PHA_khong_doc_co(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            kc = fh.read()
        i = kc.find("    def dang_lam_viec_vat(")
        self.assertGreater(i, 0, "mat phep hoi 'co dang giua viec vat khong'")
        than = kc[i:kc.find("\n    def ", i + 10)]
        self.assertIn("get_account_task(", than)
        self.assertIn("PHASE_LOGIN_CHORE", than)
        # Soi phan CODE (bo docstring - no co ke lai chuyen cai co cu).
        import ast, textwrap
        fn = ast.parse(textwrap.dedent(than)).body[0]
        ma = "\n".join(ast.dump(n) for n in (fn.body[1:] if ast.get_docstring(fn) else fn.body))
        self.assertNotIn("party_invite_ready", ma, "lai doc co gan tay -> van ket duoc")

    def test_dieu_phoi_BIET_acc_dang_viec_vat_va_KHONG_pha_doi(self):
        """Dieu phoi VAN ra lenh moi (leader cu moi, loi moi duoc giu lai) - chi KHONG bump reform."""
        i = self.src.find("THIEU NGUOI VI CO ACC DANG LAM VIEC VAT -> KHONG PHA DOI.")
        self.assertGreater(i, 0, "dieu phoi khong biet acc dang viec vat -> bump reform pha doi")
        khoi = self.src[i:i + 1800]
        self.assertIn("_ban = _ai_dang_lam_viec_le(song)", khoi)
        self.assertIn("return None", khoi)
        # va phai dat TRUOC cho bump
        _bump = self.src.find('_bump_reform(st, "chung kenh roi ma doi khong du')
        self.assertGreater(_bump, i, "cua chan dat SAU bump -> vo nghia")

    def test_dieu_phoi_KHONG_con_bac_cho_viec_le(self):
        self.assertNotIn("_ai_dang_lam_viec_le(st, song)", self.src,
                         "lai chan dieu phoi ra lenh vi co acc ban -> ket o thanh")
        # (Chuoi "dang lam viec LE hop le" van con trong docstring ke lai ca hong - hop le.)
        _ma = [ln for ln in self.src.splitlines()
               if "dang lam viec LE hop le" in ln and not ln.lstrip().startswith(("#", "'", '"'))
               and "ly_do" in ln]
        self.assertEqual(_ma, [], "bac cho viec le song lai: %s" % _ma)

    def test_KHONG_con_han_cho(self):
        """Het han thi hoac keo acc di (hong viec vat) hoac cho tiep (ket o thanh) - deu sai."""
        for _t in ("CHO_VIEC_LE_TOI_DA_SEC", "VIEC_LE_TOI_DA_SEC", "cho_viec_le_tu"):
            self.assertNotIn(_t, self.src, "han cho song lai: %s" % _t)

    def test_ham_viec_vat_KHONG_dung_de_NGUNG_RA_LENH(self):
        i = self.src.find("def _ai_dang_lam_viec_le(")
        self.assertGreater(i, 0)
        than = self.src[i:self.src.find("\ndef ", i + 10)]
        self.assertIn("get_account_task(", than)
        self.assertNotIn("time.time()", than, "ham in log ma lai co dong ho -> no dang quyet dinh gi do")
        # chi duoc GOI tu dung mot cho (dong log trang thai); dong con lai la `def`
        _goi = [ln.strip() for ln in self.src.splitlines()
                if "_ai_dang_lam_viec_le(song)" in ln and not ln.lstrip().startswith("def ")]
        # BON cho, va KHONG cho nao duoc dung de NGUNG RA LENH:
        #   `_le = set(...)`          -> danh dau `*` tren dong TRANG THAI
        #   `_ban = ...`              -> KHONG bump reform (van ra lenh moi binh thuong)
        #   `_ban_viec_vat = set(...)`-> khong tinh acc do vao phep do LECH MAP / LECH KENH
        #   `_ban = set(...)` (thi hanh kenh) -> KHONG gui lenh doi kenh cho acc dang viec vat
        #
        # Cai thu tu la ve cua user 14/09: "khi dang danh PB don va daily quest thi dieu phoi tam
        # thoi ko quay ray". No chi bo qua acc do trong MOT luot gui lenh, khong dung lenh lai.
        #
        # Cai thu ba KHONG phai "cho": viec vat PHAI o map khac (ban Noi Dat o Nghiep Thanh, cat
        # tien trang, boss the gioi - user 14/09), nen dem no vao `maps` la party LUC NAO cung
        # "lech map". Lenh van chay binh thuong tren so acc con lai; acc kia GIU loi moi, xong
        # viec thi nhan.
        self.assertEqual(len(_goi), 4, "so cho goi doi -> co the co cho dung no de ngung ra lenh")
        for _dau in ("_le = set(", "_ban = ", "_ban_viec_vat = set("):
            self.assertTrue(any(_dau in g for g in _goi), "%s: %s" % (_dau, _goi))

    def test_chuoi_bac_dung_thu_tu_user_chot(self):
        """lech map -> dong bo map -> lech kenh -> dong bo kenh -> lap pt -> di train."""
        _thu_tu = ["elif song and len(maps) > 1:",
                   "elif song and _chua_biet_map:",
                   "elif song and _thieu_doi(pidx, song) and _ai_lech_instance(pidx, song):",
                   "elif song and len(kenhs) > 1 and _thieu_doi(pidx, song):",
                   "elif song and _thieu_doi(pidx, song):"]
        _vt = []
        for _b in _thu_tu:
            j = self.src.find(_b)
            self.assertGreater(j, 0, "mat bac %r" % _b)
            _vt.append(j)
        self.assertEqual(_vt, sorted(_vt), "chuoi bac dieu phoi sai thu tu")


class TestMotDuaRotKhongPhaCaDoi(unittest.TestCase):
    def setUp(self):
        self.src = _src()

    def test_chi_giai_tan_khi_party_DA_HONG(self):
        i = self.src.find("KHONG GIAI TAN PARTY chi vi MOT dua rot")
        self.assertGreater(i, 0, "mot dua rot van pha ca doi dang lanh")
        khoi = self.src[i:i + 1400]
        self.assertIn('if is_leader and not getattr(c, "party_members", None):', khoi)

    def test_van_con_duong_cho_reconnect(self):
        """Bo giai tan khong duoc lam mat vong cho dong doi ve."""
        self.assertIn('while st["reconnecting"] and c.running and not _stopped():', self.src)


class TestDoiDuChuaDocROSTER_LEADER(unittest.TestCase):
    def setUp(self):
        self.src = _src()

    def test_thieu_doi_doc_leader(self):
        i = self.src.find("def _thieu_doi(")
        than = self.src[i:self.src.find("\ndef ", i + 10)]
        self.assertIn("config.PARTY_LEADER_ACC.get(pidx)", than,
                      "van lay ban sao ngheo nhat -> doi du van bi doc thanh thieu")

    def test_leader_khong_chay_thi_lay_ban_sao_day_du_nhat(self):
        i = self.src.find("def _thieu_doi(")
        than = self.src[i:self.src.find("\ndef ", i + 10)]
        self.assertIn("_max", than)


class TestDongLogTrangThai(unittest.TestCase):
    """Mot dong du de dung lai ca canh - khoi ghep 5 lenh grep moi lan truy loi."""

    def setUp(self):
        self.src = _src()

    def test_co_ham_log_trang_thai(self):
        self.assertIn("def _log_trang_thai(", self.src)

    def test_in_kem_moi_lan_lenh_doi(self):
        i = self.src.find("def _ghi_ke_hoach(")
        than = self.src[i:self.src.find("\ndef ", i + 10)]
        self.assertIn("_log_trang_thai(st, pidx)", than)

    def test_co_du_map_kenh_roster_reform(self):
        i = self.src.find("def _log_trang_thai(")
        than = self.src[i:self.src.find("\ndef ", i + 10)]
        for _k in ("current_map", "current_channel", "party_members", "reform_gen",
                   "reform_gen_thoa"):
            self.assertIn(_k, than, _k)

    def test_khong_duoc_nem_loi(self):
        """Log hong khong duoc lam chet vong dieu phoi."""
        i = self.src.find("def _log_trang_thai(")
        than = self.src[i:self.src.find("\ndef ", i + 10)]
        self.assertIn("except Exception", than)

    def test_chay_that_khong_nem(self):
        class _C:
            current_map = 21833
            current_channel = 1
            party_members = [b"x" * 8] * 4
            _label = "thbay"
            running = True
        st = {"lock": threading.RLock(), "reform_gen": 3, "reform_gen_thoa": 3}
        _as = R._acc_song
        try:
            R._acc_song = lambda pidx: [("u1", _C()), ("u2", _C())]
            R._log_trang_thai(st, 0)          # khong duoc nem
        finally:
            R._acc_song = _as


if __name__ == "__main__":
    unittest.main()
