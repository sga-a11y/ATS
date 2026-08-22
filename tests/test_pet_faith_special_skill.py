"""Doc TRUNG THANH (忠誠) va CO DA MO DAC KY (武將特有技) cua tung pet.

Ca hai nam SAN trong goi PET LIST bot da nhan tu truoc (S:015-008 = 0x0f sub08) - chi la truoc
day khong doc toi. Thu tu truong theo Logic/Role.lua FollowNpcAppear:
    +26 dieCount | +27 Faith | +28 canGrow | +29 SkillPoint(2) | +31 namelen
    +32 ten | +32+nl skillLv*3 | +35+nl sublimeCount | +36+nl specialSkillLearned
3 moc +29 / +31 / +32+nl da duoc bot dung tu truoc va DUNG -> bang offset nay tin duoc.

DAC KY phai LAM NHIEM VU moi mo. Client chi cho dung khi CO CO (RoleController.lua:4786):
    if self.data.specialSkillLearned and skillDatas[npcDatas[self.npcId].specialSkill] ~= nil
Ngoai ra co goi bao NGAY luc vua mo: S:020-049 <武將學習特殊技> +武將索引(1) (0x14 sub 0x31)
-> protocal.lua:3140 followNpc.data.specialSkillLearned = true.
"""
import unittest
from pathlib import Path

from bot.client import GameClient

ROOT = Path(__file__).resolve().parents[1]


def pet_record(marker, pid, name, faith, special, skill_lv=(1, 2, 3), level=45, skill_point=7):
    """Dung 1 ban ghi pet y het layout that (dai 254 + namelen)."""
    nl = len(name) * 2
    r = bytearray(254 + nl)
    r[0] = marker
    r[1:3] = pid.to_bytes(2, "little")
    r[7] = level
    r[27] = faith
    r[29:31] = skill_point.to_bytes(2, "little")
    r[31] = nl
    r[32:32 + nl] = name.encode("utf-16-le")
    r[32 + nl:35 + nl] = bytes(skill_lv)
    r[35 + nl] = 0                              # sublimeCount
    r[36 + nl] = 1 if special else 0            # specialSkillLearned
    return bytes(r)


class _State:
    def __init__(self):
        self.active_pet_id = None
        self.carried_pets = []
        self.multi_pet_skills = {}
        self.pet = None


def make_client():
    c = GameClient.__new__(GameClient)
    c._label = "tl706"
    c.running = True
    c.pet_faith = {}
    c.pet_special_skill = {}
    c.state = _State()
    c.self_entity = None
    c.active_pet_slot = None
    c._pet_marker_to_atype = lambda m: None
    c.save_skill_cache = lambda *a, **k: None
    c.skills_snapshot = lambda *a, **k: None
    c._refresh_active_pet_login_stats = lambda *a, **k: None
    c._observe_npc40_packet = lambda *a: None
    c._observe_mob_packet = lambda *a: None
    c._track_battle_packet = lambda *a: None
    return c


class TestPetFaithSpecialSkill(unittest.TestCase):
    def test_doc_tu_goi_pet_list(self):
        c = make_client()
        body = (b"\x00\x00" + bytes([2])
                + pet_record(1, 0xA051, "Thai", 92, True)
                + pet_record(2, 0xA0DB, "Ngo", 41, False))
        GameClient._on_pet_list(c, b"\x00" * 7 + body)
        self.assertEqual(c.pet_faith, {0xA051: 92, 0xA0DB: 41})
        self.assertEqual(c.pet_special_skill, {0xA051: True, 0xA0DB: False})

    def test_ten_pet_dai_ngan_khac_nhau_van_dung_offset(self):
        """Offset cua 2 truong phu thuoc namelen -> thu ten dai/ngan de chac khong lech."""
        for ten in ("A", "Thai Van Co", "Ten That Dai Cua Mot Con Pet"):
            c = make_client()
            body = b"\x00\x00" + bytes([1]) + pet_record(1, 0xA051, ten, 55, True)
            GameClient._on_pet_list(c, b"\x00" * 7 + body)
            self.assertEqual(c.pet_faith.get(0xA051), 55, "lech voi ten %r" % ten)
            self.assertIs(c.pet_special_skill.get(0xA051), True, "lech voi ten %r" % ten)

    def test_goi_bao_VUA_MO_dac_ky(self):
        """S:020-049 cho INDEX vo tuong (slot mang theo), khong cho pet_id."""
        c = make_client()
        c.state.carried_pets = [(0xA051, ""), (0xA0DB, "")]
        c.pet_special_skill = {0xA051: True, 0xA0DB: False}
        GameClient._dispatch(c, 0x14, b"\x00" * 7 + b"\x31\x00" + bytes([2]))
        self.assertIs(c.pet_special_skill[0xA0DB], True)

    def test_index_ngoai_pham_vi_khong_lam_sap(self):
        c = make_client()
        c.state.carried_pets = [(0xA051, "")]
        GameClient._dispatch(c, 0x14, b"\x00" * 7 + b"\x31\x00" + bytes([9]))
        self.assertEqual(c.pet_special_skill, {})


class TestPetUsableSkills(unittest.TestCase):
    """Dac ky chi duoc dua vao danh sach khi DU CA HAI dieu kien (giong client)."""

    def test_chi_them_dac_ky_khi_DA_MO(self):
        from bot import config as C
        # phai chon con ma bot CO du lieu skill dac ky, khong thi bi loai dung theo thiet ke
        pid = next(p for p, sk in C.PET_SPECIAL_SKILL.items()
                   if C.PET_SKILLS.get(p) and sk in C.SKILL_INFO)
        sp = C.PET_SPECIAL_SKILL[pid]
        c = make_client()

        c.pet_special_skill = {pid: False}
        self.assertNotIn(sp, c.pet_usable_skills(pid))

        c.pet_special_skill = {pid: True}
        self.assertEqual(c.pet_usable_skills(pid), list(C.PET_SKILLS[pid]) + [sp])

    def test_KHONG_dung_dac_ky_khi_bot_chua_co_du_lieu_skill(self):
        """Dua skill la vao combat = chon mu (khong biet cost/splash). Thieu du lieu -> bo qua."""
        from bot import config as C
        la = [p for p, sk in C.PET_SPECIAL_SKILL.items()
              if sk not in C.SKILL_INFO and C.PET_SKILLS.get(p)]
        if not la:
            self.skipTest("skills_data.json da phu het dac ky")
        pid = la[0]
        c = make_client()
        c.pet_special_skill = {pid: True}
        self.assertEqual(c.pet_usable_skills(pid), list(C.PET_SKILLS[pid]))
        self.assertNotIn(C.PET_SPECIAL_SKILL[pid], c.pet_usable_skills(pid))

    def test_combat_lay_skill_qua_pet_usable_skills(self):
        """3 cho combat lay skill pet phai goi pet_usable_skills, khong lay thang PET_SKILLS."""
        src = (ROOT / "bot/client.py").read_text(encoding="utf-8")
        self.assertIn("self.state.pet_skills = self.pet_usable_skills(pid)", src)
        self.assertIn("self.state.pet_skills = self.pet_usable_skills(chosen_pid)", src)
        self.assertIn("sk = self.pet_usable_skills(pid)", src)

    def test_pet_khong_co_trong_bang_thi_rong(self):
        c = make_client()
        c.pet_special_skill = {0xFFFF: True}
        self.assertEqual(c.pet_usable_skills(0xFFFF), [])

    def test_bang_dac_ky_nap_duoc_va_hop_le(self):
        from bot import config as C
        self.assertGreater(len(C.PET_SPECIAL_SKILL), 100,
                           "npc_special_skill.json chua duoc sinh / khong nap duoc")
        # skill id nam trong dai skill (giong SK_LO/SK_HI cua tool crack)
        for _pid, _sk in list(C.PET_SPECIAL_SKILL.items())[:200]:
            self.assertTrue(0x2710 <= _sk <= 0x7FFF, "dac ky ngoai dai: 0x%04x" % _sk)


class TestCombatDungDacKy(unittest.TestCase):
    """Chuoi day du: goi pet list -> co -> bang skill -> state.pet_skills -> COMBAT CHON duoc."""

    def test_combat_chon_dac_ky_khi_no_la_lua_chon_tot_nhat(self):
        from bot import combat, config as C
        from bot.state import BattleState

        def all_target(sk):
            return C.SKILL_INFO.get(sk, {}).get("splash") == 8

        # chon con ma DAC KY la lua chon all-target DUY NHAT -> neu bot chon no thi chac chan
        # la nho dac ky, khong phai trung voi skill thuong
        cand = [(p, sk) for p, sk in C.PET_SPECIAL_SKILL.items()
                if all_target(sk) and C.PET_SKILLS.get(p)
                and not any(all_target(x) for x in C.PET_SKILLS[p])]
        if not cand:
            self.skipTest("khong co pet nao thoa dieu kien")
        pid, sp = cand[0]

        def quyet_dinh(skills):
            st = BattleState()
            st.my_atype = 2
            st.quest_mode = True                       # dong quai -> uu tien all-target
            st.enemy_slots = {i: 500 for i in range(8)}
            st.enemy_gen = 1
            st.pet_skills = list(skills)
            st.pet = type("U", (), {"hp": 1900, "hp_max": 1900, "sp": 460, "sp_max": 460})()
            d = combat.decide_pet(st, options=[(2, t) for t in range(5)])
            return getattr(d, "skill", None)

        base = list(C.PET_SKILLS[pid])
        self.assertNotEqual(quyet_dinh(base), sp, "chua mo ma da chon dac ky")
        self.assertEqual(quyet_dinh(base + [sp]), sp, "da mo ma combat KHONG chon dac ky")


class TestAllTargetChonDatNhat(unittest.TestCase):
    """all-target: lay DAT NHAT (manh nhat) trong tam SP, khong lay re nhat nhu truoc."""

    @staticmethod
    def _pet_co_ca_hai():
        from bot import config as C

        def sp8(sk):
            return C.SKILL_INFO.get(sk, {}).get("splash") == 8

        def gia(sk):
            return C.SKILL_INFO.get(sk, {}).get("cost", 0)

        for p, sk in C.PET_SPECIAL_SKILL.items():
            base = C.PET_SKILLS.get(p) or []
            re_nhat = [x for x in base if sp8(x)]
            if sp8(sk) and re_nhat and gia(sk) > min(gia(x) for x in re_nhat):
                return p, sk, min(re_nhat, key=gia)
        return None, None, None

    def test_du_SP_lay_DAT_nhat_thieu_SP_lay_RE_nhat(self):
        from bot import combat, config as C
        pid, sp, re_nhat = self._pet_co_ca_hai()
        if pid is None:
            self.skipTest("khong co pet nao co ca 2 loai all-target")
        sks = list(C.PET_SKILLS[pid]) + [sp]
        gia = lambda x: C.SKILL_INFO[x]["cost"]
        self.assertEqual(combat.pick_alltarget_skill(sks, 10000), sp)      # du SP -> dat nhat
        self.assertEqual(combat.pick_alltarget_skill(sks, gia(sp)), sp)    # vua du -> van dat nhat
        # THIEU SP: phai tra RE NHAT de caller tu loai, KHONG duoc tra dat nhat (se mat ca nhanh
        # all-target -> roi xuong danh thuong du dang co skill re dung duoc)
        self.assertEqual(combat.pick_alltarget_skill(sks, gia(sp) - 1), re_nhat)
        self.assertEqual(combat.pick_alltarget_skill(sks), sp)             # khong xet SP -> dat nhat

    def test_qua_COMBAT_that_trong_PB_dong_quai(self):
        from bot import combat, config as C
        from bot.state import BattleState
        pid, sp, re_nhat = self._pet_co_ca_hai()
        if pid is None:
            self.skipTest("khong co pet nao co ca 2 loai all-target")

        def danh(sp_hien_co):
            st = BattleState()
            st.my_atype = 2
            st.quest_mode = True                        # PB dat quest_mode (client.py:8444)
            st.enemy_slots = {i: 500 for i in range(8)}  # >6 quai -> nhanh all-target
            st.enemy_gen = 1
            st.pet_skills = list(C.PET_SKILLS[pid]) + [sp]
            st.pet = type("U", (), {"hp": 1900, "hp_max": 1900,
                                    "sp": sp_hien_co, "sp_max": 460})()
            return getattr(combat.decide_pet(st, options=[(2, t) for t in range(5)]), "skill", None)

        self.assertEqual(danh(400), sp, "du SP ma khong dung dac ky")
        self.assertEqual(danh(C.SKILL_INFO[sp]["cost"] - 6), re_nhat,
                         "thieu SP thi phai dung skill all-target re, khong duoc mat luot")


if __name__ == "__main__":
    unittest.main()
