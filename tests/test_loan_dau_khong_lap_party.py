"""LOAN DAU la SOLO - dieu phoi KHONG duoc ra lenh cap party (lap lai doi / doi kenh).

User 10/09: "P21 lam gi ma thay lap pt".

Party 21 = mode `event` + `event_key=loan_dau`, dang giua gio loan dau thu 5:

    21:09:30 [party 21] DIEU PHOI: ca party da chung kenh 1 nhung DOI chua du
                        (dieu906=4 dieu907=1 dieu908=2 dieu909=3 dieu910=4) -> LAP LAI PARTY
    21:11:31 ... 21:13:31 ... 21:15:31 ... 21:17:32     (moi 2 phut, dung bang LAP_LAI_PARTY_COOLDOWN)

Loan dau khong bao gio "du doi": moi acc TU dang ky, TU danh; con so roster la rac (moi acc thay
mot kieu: 4/1/2/3/4). Bump reform lien tuc giua luc dang cho ghep tran = abort acc dang doi, mat
luot - dung ca da ghi trong `_dieu_phoi_chot_kenh`:
    20:23:14 [haba] Loan dau: da dang ky, cho ghep tran (thang=0)   <- dang ky o KENH 4
    20:23:19 [haba] Doi kenh OK -> 2                                <- dieu phoi keo sang kenh 2
    20:38:14 [haba] Loan dau: cho ghep tran qua 900s khong vao -> dung

NGUYEN NHAN: guard loan dau CO SAN nhung nam o CUOI ham, sau ca nhanh "chung kenh ma doi khong du
-> LAP LAI PARTY". Cua chan dat SAU dung cai viec no phai chan (L3h).
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

from bot import config


class _C:
    def __init__(self, ch=1, roster=0, map_id=10991):
        self.running = True
        self.current_map = map_id
        self.current_channel = ch
        self.party_members = [b"x" * 8] * roster
        self._chan_switch_result = None
        self._chan_switch_target = None
        self._chan_switch_luc = 0.0
        self._ds_kenh_nhan_luc = 0.0
        self._ds_kenh_hoi_luc = 0.0
        self.channels = {}

    def in_combat(self, *_a, **_k):
        return False

    def digioi_minutes_live(self):
        return 0.0

    def request_channel_list(self):
        pass


class _Nen(unittest.TestCase):
    PARTY = 0
    ACCS = ("a1", "a2", "a3")

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", u == "a1", u == "a1") for u in self.ACCS]
        self._jmc = R.joined_member_count
        R.joined_member_count = lambda pidx: 0        # doi RONG -> se doi lap lai party
        self._cl = dict(R.account_clients)
        R.account_clients.clear()
        R._party_state.pop(self.PARTY, None)
        self._pcfg = dict(getattr(config, "PARTY_CONFIG", {}))
        self._evs = dict(getattr(config, "EVENTS", {}) or {})
        self._eht = config.event_hom_nay
        config.PARTY_CONFIG = {self.PARTY: {"mode": "event", "event_key": "loan_dau"}}
        config.EVENTS = {"loan_dau": {"label": "Loan dau",
                                      "party_battle": {"kind": "chaos_vs"}}}
        config.event_hom_nay = lambda k: config.EVENTS.get(k)

    def tearDown(self):
        R.party_accounts = self._pa
        R.joined_member_count = self._jmc
        R.account_clients.clear(); R.account_clients.update(self._cl)
        R._party_state.pop(self.PARTY, None)
        config.PARTY_CONFIG = self._pcfg
        config.EVENTS = self._evs
        config.event_hom_nay = self._eht

    def _song(self, **kw):
        for u, c in kw.items():
            R.account_clients[u] = c
        return [(u, R.account_clients[u]) for u in self.ACCS if u in R.account_clients]


class TestNhanDienLoanDau(_Nen):
    def test_loan_dau_KHONG_can_lap_doi(self):
        self.assertFalse(R._mode_can_lap_doi(self.PARTY))

    def test_mode_train_THI_CAN(self):
        config.PARTY_CONFIG = {self.PARTY: {"mode": "train"}}
        self.assertTrue(R._mode_can_lap_doi(self.PARTY))

    def test_event_KHAC_THI_CAN(self):
        """40NPC / 2K van lap party binh thuong - khong duoc tat nham."""
        for kind in ("npc_repeat", "floor_crawl"):
            config.EVENTS = {"e": {"party_battle": {"kind": kind}}}
            config.PARTY_CONFIG = {self.PARTY: {"mode": "event", "event_key": "e"}}
            self.assertTrue(R._mode_can_lap_doi(self.PARTY), kind)

    def test_KHONG_BIET_thi_coi_la_CAN(self):
        """Doc config loi -> giu hanh vi cu, khong tat nham duong lap doi cua party thuong."""
        _cu = config.event_hom_nay
        config.event_hom_nay = lambda k: (_ for _ in ()).throw(RuntimeError("hong"))
        try:
            self.assertTrue(R._mode_can_lap_doi(self.PARTY))
        finally:
            config.event_hom_nay = _cu


class TestKhongRaLenhCapParty(_Nen):
    def test_KHONG_lap_lai_party_du_doi_RONG(self):
        st = R._pstate(self.PARTY)
        gen = st["reform_gen"]
        song = self._song(a1=_C(1), a2=_C(1), a3=_C(1))     # cung kenh, doi rong
        R._dieu_phoi_chot_kenh(self.PARTY, st, song)
        self.assertEqual(st["reform_gen"], gen,
                         "bump reform giua luc dang cho ghep tran = abort acc, mat luot")

    def test_KHONG_chot_kenh_dich_du_LECH_KENH(self):
        st = R._pstate(self.PARTY)
        song = self._song(a1=_C(1), a2=_C(4), a3=_C(9))
        self.assertIsNone(R._dieu_phoi_chot_kenh(self.PARTY, st, song))
        self.assertIsNone(st.get("kenh_dich"))

    def test_BO_kenh_dich_con_treo(self):
        """Kenh dich chot tu truoc khi vao gio loan dau phai duoc go, khong keo acc di nua."""
        st = R._pstate(self.PARTY)
        with st["lock"]:
            st["kenh_dich"] = 7
        song = self._song(a1=_C(1), a2=_C(4), a3=_C(9))
        R._dieu_phoi_chot_kenh(self.PARTY, st, song)
        self.assertIsNone(st.get("kenh_dich"))

    def test_party_TRAIN_van_lap_lai_party_binh_thuong(self):
        """Chan nham ca party thuong thi khong con ai gom doi."""
        config.PARTY_CONFIG = {self.PARTY: {"mode": "train"}}
        st = R._pstate(self.PARTY)
        gen = st["reform_gen"]
        song = self._song(a1=_C(1), a2=_C(1), a3=_C(1))
        R._dieu_phoi_chot_kenh(self.PARTY, st, song)
        self.assertGreater(st["reform_gen"], gen, "party train ma khong lap lai doi")


class TestKeHoachKhongRaLenhCapParty(_Nen):
    """`_dieu_phoi_quyet` moi la CHO SINH RA `viec=moi` / `gom` / `dong_bo`.

    Lan sua dau toi chi chan o `_dieu_phoi_chot_kenh` -> party 24 van ra du ba lenh do:
        21:29:49 gen 2:  viec=moi     - cung map/kenh nhung DOI chua du (daim01=0 daim02=0 ...)
        21:12:23 gen 12: viec=gom     - party dang o 2 MAP khac nhau [10991, 12003]
        21:12:27 gen 13: viec=dong_bo - party lech kenh [1, 2]
    """

    def _quyet(self, lech_tu=None, **kw):
        song = self._song(**kw)
        return R._dieu_phoi_quyet(self.PARTY, R._pstate(self.PARTY), song, lech_tu)

    def test_doi_RONG_van_KHONG_ra_lenh_MOI(self):
        kh, ly_do, _ = self._quyet(a1=_C(1), a2=_C(1), a3=_C(1))
        self.assertEqual(kh["viec"], R.VIEC_LAM, ly_do)

    def test_LECH_MAP_van_KHONG_ra_lenh_GOM(self):
        """10991 = map loan dau, 12003 = Quang Truong. Acc chua vao la viec cua chinh no."""
        kh, ly_do, _ = self._quyet(lech_tu=1.0, a1=_C(1, map_id=10991),
                                   a2=_C(1, map_id=12003), a3=_C(1, map_id=12003))
        self.assertEqual(kh["viec"], R.VIEC_LAM, ly_do)

    def test_LECH_KENH_van_KHONG_ra_lenh_DONG_BO(self):
        kh, ly_do, _ = self._quyet(lech_tu=1.0, a1=_C(1), a2=_C(2), a3=_C(2))
        self.assertEqual(kh["viec"], R.VIEC_LAM, ly_do)

    def test_ly_do_noi_ro_LA_MODE_khong_phai_tinh_huong(self):
        _kh, ly_do, _ = self._quyet(a1=_C(1), a2=_C(1), a3=_C(1))
        self.assertIn("KHONG CAN LAP DOI", ly_do)

    def test_party_TRAIN_lech_map_VAN_ra_lenh_gom(self):
        config.PARTY_CONFIG = {self.PARTY: {"mode": "train"}}
        kh, ly_do, _ = self._quyet(lech_tu=1.0, a1=_C(1, map_id=21001),
                                   a2=_C(1, map_id=12061), a3=_C(1, map_id=12061))
        self.assertEqual(kh["viec"], R.VIEC_GOM, ly_do)


class TestSoMemberCanCho(unittest.TestCase):
    """GOC: mode khong co viec lap doi thi `n_members` = 0.

    Khong phai "chan cho khoi moi" - mode do THAT SU khong can cho ai. Dat dung con so nay thi MOI
    vong "chua du member -> moi lai / gom / reform" tu tat, khong phai di va tung cho.

    Ca that party 19 (10/09): `n_members = 4` cho mode loan dau -> leader lap doi day 4/4 -> vao
    nhanh "DU 4/4 member -> SET QS + ra train" -> `UnboundLocalError: _start_training` (ham do chi
    duoc `def` tren duong train, mode nay khong di qua) - lap moi phut.
    """

    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_n_members_hoi_mode_truoc_khi_dem(self):
        i = self.src.find('st["n_members"] = ')
        self.assertGreater(i, 0)
        self.assertIn("_mode_can_lap_doi(pidx)", self.src[i:i + 300],
                      "dem member cho mode khong can doi = ca chuoi 'chua du member' chay oan")

    def test_chi_dat_o_MOT_cho(self):
        self.assertEqual(self.src.count('st["n_members"] = '), 1)

    def test_chay_that_loan_dau_ra_0(self):
        from bot import config as _cf
        _pcfg, _evs, _eht = (dict(getattr(_cf, "PARTY_CONFIG", {})),
                             dict(getattr(_cf, "EVENTS", {}) or {}), _cf.event_hom_nay)
        _pa = R.party_accounts
        try:
            _cf.EVENTS = {"ld": {"party_battle": {"kind": "chaos_vs"}}}
            _cf.event_hom_nay = lambda k: _cf.EVENTS.get(k)
            R.party_accounts = lambda pidx: [("a%d" % i, "p", i == 0, i == 0) for i in range(5)]
            _cf.PARTY_CONFIG = {0: {"mode": "event", "event_key": "ld"}}
            self.assertFalse(R._mode_can_lap_doi(0))
            _cf.PARTY_CONFIG = {0: {"mode": "train"}}
            self.assertTrue(R._mode_can_lap_doi(0))
        finally:
            _cf.PARTY_CONFIG, _cf.EVENTS, _cf.event_hom_nay = _pcfg, _evs, _eht
            R.party_accounts = _pa


class TestPhiaThiHanhDocDUNGLenh(unittest.TestCase):
    """Lenh dieu phoi la TUYET DOI - phia thi hanh phai doc DUNG, khong tu suy.

    User 10/09: "lenh cua dieu phoi la tuyet doi nen deo duoc chan, no ra lenh sai thi phai sua cho
    no ra lenh dung". O ca party 19 lenh KHONG sai (`viec=lam`) - phia doc sai: vong moi party chi
    xet MOT lenh (`VIEC_GOM`), moi lenh khac deu bi hieu thanh "cu moi".
    """

    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()
        i = self.src.find("def _moi_theo_dieu_phoi(")
        self.assertGreater(i, 0)
        j = self.src.find("\n        def ", i + 10)
        self.than = self.src[i:j if j > i else len(self.src)]

    def test_loan_dau_tat_vong_moi_TU_GOC_bang_n_members(self):
        """Khong chan o vong moi (chan la chan oan ca party thuong - xem party 1, 10/09).

        Mode khong co viec lap doi thi `n_members = 0`, nen `while joined < n_members` khong chay
        lan nao. Tat tu goc, khong phai chan tung cho.
        """
        i = self.src.find('st["n_members"] = ')
        self.assertGreater(i, 0)
        self.assertIn("_mode_can_lap_doi(pidx)", self.src[i:i + 300])

    def test_van_giu_duong_thoi_moi_khi_bao_GOM(self):
        self.assertIn('_kh.get("viec") == VIEC_GOM', self.than)

    def test_ham_moi_KHONG_tu_quyet(self):
        """`_invite_party_participants` chi THI HANH - quyet dinh la cua dieu phoi."""
        i = self.src.find("def _invite_party_participants(")
        j = self.src.find("\ndef ", i + 10)
        than = self.src[i:j]
        self.assertNotIn("_mode_can_lap_doi", than,
                         "ham thi hanh ma tu quyet = them mot cho co the lech voi dieu phoi")


class TestMotNGUON_SU_THAT(unittest.TestCase):
    """"Mode nay co can lap doi khong" phai la MOT ham, khong phai guard rai rac tung cho.

    User 10/09: "ko phai chan, ma dieu phoi phai biet mode nay deo can lap pt". Guard rai rac thi
    moi cho la mot dip quen - va da quen that (chan `_dieu_phoi_chot_kenh` roi bo sot
    `_dieu_phoi_quyet`).
    """

    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_chi_co_MOT_ham_tra_loi_cau_hoi_do(self):
        self.assertEqual(self.src.count("def _mode_can_lap_doi("), 1)

    def test_ca_HAI_duong_ra_lenh_deu_hoi_ham_do(self):
        for _ham in ("def _dieu_phoi_quyet(", "def _dieu_phoi_chot_kenh("):
            i = self.src.find(_ham)
            self.assertGreater(i, 0, _ham)
            j = self.src.find("\ndef ", i + 10)
            self.assertIn("_mode_can_lap_doi(pidx)", self.src[i:j], _ham)


class TestThuTuGuard(unittest.TestCase):
    """Cua chan phai dung TRUOC viec no chan (L3h) - dung loi da mac o day."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()
        i = self.src.find("def _dieu_phoi_chot_kenh(")
        self.assertGreater(i, 0)
        j = self.src.find("\ndef ", i + 10)
        self.than = self.src[i:j]

    def test_guard_loan_dau_dung_TRUOC_nhanh_lap_lai_party(self):
        i_guard = self.than.find("_mode_can_lap_doi(pidx)")
        i_lap = self.than.find("chung kenh roi ma doi khong du -> lap lai party")
        self.assertGreater(i_guard, 0, "mat guard loan dau")
        self.assertGreater(i_lap, 0)
        self.assertLess(i_guard, i_lap,
                        "guard nam SAU nhanh lap lai party = khong chan duoc gi (ca party 21)")

    def test_guard_loan_dau_dung_TRUOC_moi_cho_chot_kenh(self):
        i_guard = self.than.find("_mode_can_lap_doi(pidx)")
        for _moc in ("CHOT kenh dich", "_lam_moi_ds_kenh(", "_doc_ket_qua_doi_kenh("):
            i = self.than.find(_moc)
            if i > 0:
                self.assertLess(i_guard, i, "guard phai dung truoc '%s'" % _moc)


if __name__ == "__main__":
    unittest.main()
