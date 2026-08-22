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

from bot.client import GameClient


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
        pid = next(p for p in C.PET_SPECIAL_SKILL if C.PET_SKILLS.get(p))
        sp = C.PET_SPECIAL_SKILL[pid]
        c = make_client()

        c.pet_special_skill = {pid: False}
        self.assertNotIn(sp, c.pet_usable_skills(pid))

        c.pet_special_skill = {pid: True}
        self.assertEqual(c.pet_usable_skills(pid), list(C.PET_SKILLS[pid]) + [sp])

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


if __name__ == "__main__":
    unittest.main()
