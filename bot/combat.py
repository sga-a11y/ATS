"""Logic AI combat - quyet dinh skill + target moi luot.

atype=1 (gia tri server chap nhan cho bot; atype 2/3 bi da khoi tran).
Quy tac skill:
  CHAR (unit 3): SP>=100 -> Hoa Tien (AOE 3 hang ngang); ally HP<=60% -> Toan Tri Lieu; con lai -> danh thuong
  PET  (unit 2): SP>=15 -> Hoa Tien; con lai -> danh thuong

Target Hoa Tien (AOE 3 o hang ngang, trung [t-1, t, t+1]):
  - Chon o phu NHIEU quai nhat. Hoa -> uu tien o sau (bo qua con dau hang).
  - 3 con sat nhau -> con giua; 2 con sat nhau -> con thu 2.
Target skill don (danh thuong/hoa tien khong AOE) -> focus con it mau nhat.
"""
from . import config

# atype = VI TRI FORMATION cua member (leader o giua). Tinh tu roster, luu o state.my_atype.
# vd: 2 member + leader -> member1=vi tri 1 (atype1), leader=2, member2=vi tri 3 (atype3).
# Sai atype = bi server da (slot strict).


class Decision:
    def __init__(self, unit, atype, target, skill):
        self.unit = unit
        self.atype = atype
        self.target = target
        self.skill = skill

    def __repr__(self):
        return f"Decision(unit={self.unit} atype={self.atype} target={self.target} skill={self.skill})"


def _offered_targets(options, atype):
    """Cac target hop le cho atype dang dung (server liet ke trong 0x35)."""
    t = [o[1] for o in options if o[0] == atype]
    return t or [o[1] for o in options]


def _same_row(a, b):
    """Game: toi da 10 quai, 2 hang x 5 con. Hang = slot//5 (slot 0-based: 0-4 hang 0, 5-9 hang 1).
    Slot 4 va 5 KHONG cung hang."""
    return a // 5 == b // 5


def _aoe_target(enemy_slots, offered):
    """Chon target theo uu tien (CHI chon trong cac o duoc phep = offered, tranh loi 2a):
      1. Nhom 3 con lien nhau (cung hang) DAU TIEN -> con GIUA nhom 3 do
      2. Khong co nhom 3 -> nhom 2 con lien nhau dau tien -> con VI TRI THAP NHAT
      3. Chi con le -> con VI TRI THAP NHAT
    Target chon ra phai nam trong 'offered'; neu khong, fallback o offered hop le.
    """
    off = set(offered)
    es = set(enemy_slots)
    if not es:
        return offered[0] if offered else None
    s = sorted(es)
    # 1) nhom 3 lien tiep cung hang -> con giua (neu duoc phep target)
    for a in s:
        if (a + 1) in es and (a + 2) in es and _same_row(a, a + 2) and (a + 1) in off:
            return a + 1
    # 2) nhom 2 lien tiep cung hang -> con thap nhat (uu tien a, roi a+1)
    for a in s:
        if (a + 1) in es and _same_row(a, a + 1):
            if a in off:
                return a
            if (a + 1) in off:
                return a + 1
    # 3) le -> con quai thap nhat ma duoc phep target
    for t in s:
        if t in off:
            return t
    # fallback: o offered dau tien
    return offered[0] if offered else None


def _single_target(state, offered):
    """Skill don -> focus con quai it mau nhat (trong so o duoc phep + co quai)."""
    cands = [t for t in offered if t in state.enemy_slots] or offered
    if not cands:
        return None
    return min(cands, key=lambda t: state.enemy_hp.get(t, 1 << 30))


def decide_char(state, options, first_turn=False):
    at = state.my_atype
    offered = _offered_targets(options, at)
    # Hoa Tien: SP du VA nhan vat co skill nay
    if state.has_fire and state.char.sp >= config.CHAR_FIRE_MIN_SP:
        tgt = _aoe_target(state.enemy_slots, offered) or (offered[0] if offered else 1)
        return Decision(config.UNIT_CHAR, at, tgt, config.SKILL_FIRE)
    # Hoi mau toan party neu co dong doi yeu
    if state.any_ally_low(config.HEAL_HP_THRESHOLD) and state.char.sp >= 42:
        tgt = _single_target(state, offered) or (offered[0] if offered else 1)
        return Decision(config.UNIT_CHAR, at, tgt, config.SKILL_HEAL_ALL)
    # Danh thuong -> dung CUNG rule target nhu Hoa Tien (con giua/con thu 2, bo con dau)
    tgt = _aoe_target(state.enemy_slots, offered) or (offered[0] if offered else 1)
    return Decision(config.UNIT_CHAR, at, tgt, config.SKILL_NORMAL)


def decide_pet(state, options, first_turn=False):
    at = state.my_atype
    offered = _offered_targets(options, at)
    if state.pet.sp >= config.PET_FIRE_MIN_SP:
        tgt = _aoe_target(state.enemy_slots, offered) or (offered[0] if offered else 1)
        return Decision(config.UNIT_PET, at, tgt, config.SKILL_FIRE)
    # Danh thuong -> cung rule target nhu Hoa Tien
    tgt = _aoe_target(state.enemy_slots, offered) or (offered[0] if offered else 1)
    return Decision(config.UNIT_PET, at, tgt, config.SKILL_NORMAL)
