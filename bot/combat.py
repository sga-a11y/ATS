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

ATYPE = 1  # gia tri hop le cho bot


class Decision:
    def __init__(self, unit, atype, target, skill):
        self.unit = unit
        self.atype = atype
        self.target = target
        self.skill = skill

    def __repr__(self):
        return f"Decision(unit={self.unit} atype={self.atype} target={self.target} skill={self.skill})"


def _offered_targets(options):
    """Cac target hop le cho atype=1 (server liet ke trong 0x35)."""
    t = [o[1] for o in options if o[0] == ATYPE]
    return t or [o[1] for o in options]


def _same_row(a, b):
    """Game: toi da 10 quai, 2 hang x 5 con. Hang = (slot-1)//5.
    -> slot 1-5 hang 0, 6-10 hang 1. Slot 5 va 6 KHONG cung hang."""
    return (a - 1) // 5 == (b - 1) // 5


def _aoe_target(enemy_slots, offered):
    """Chon target theo uu tien:
      1. Nhom 3 con lien nhau (cung hang) DAU TIEN -> con GIUA nhom 3 do
      2. Khong co nhom 3 -> nhom 2 con lien nhau dau tien -> con VI TRI THAP NHAT
      3. Chi con le -> con VI TRI THAP NHAT
    """
    if not enemy_slots:
        return offered[0] if offered else None
    s = sorted(set(enemy_slots))
    es = set(enemy_slots)
    # 1) nhom 3 lien tiep cung hang (a, a+1, a+2) -> con giua a+1
    for a in s:
        if (a + 1) in es and (a + 2) in es and _same_row(a, a + 2):
            return a + 1
    # 2) nhom 2 lien tiep cung hang (a, a+1) -> con thap nhat a
    for a in s:
        if (a + 1) in es and _same_row(a, a + 1):
            return a
    # 3) toan le -> con thap nhat
    return s[0]


def _single_target(state, offered):
    """Skill don -> focus con quai it mau nhat (trong so o duoc phep + co quai)."""
    cands = [t for t in offered if t in state.enemy_slots] or offered
    if not cands:
        return None
    return min(cands, key=lambda t: state.enemy_hp.get(t, 1 << 30))


def decide_char(state, options, first_turn=False):
    offered = _offered_targets(options)
    # Hoa Tien: SP du
    if state.char.sp >= config.CHAR_FIRE_MIN_SP:
        tgt = _aoe_target(state.enemy_slots, offered) or (offered[0] if offered else 1)
        return Decision(config.UNIT_CHAR, ATYPE, tgt, config.SKILL_FIRE)
    # Hoi mau toan party neu co dong doi yeu
    if state.any_ally_low(config.HEAL_HP_THRESHOLD) and state.char.sp >= 42:
        tgt = _single_target(state, offered) or (offered[0] if offered else 1)
        return Decision(config.UNIT_CHAR, ATYPE, tgt, config.SKILL_HEAL_ALL)
    # Danh thuong -> dung CUNG rule target nhu Hoa Tien (con giua/con thu 2, bo con dau)
    tgt = _aoe_target(state.enemy_slots, offered) or (offered[0] if offered else 1)
    return Decision(config.UNIT_CHAR, ATYPE, tgt, config.SKILL_NORMAL)


def decide_pet(state, options, first_turn=False):
    offered = _offered_targets(options)
    if state.pet.sp >= config.PET_FIRE_MIN_SP:
        tgt = _aoe_target(state.enemy_slots, offered) or (offered[0] if offered else 1)
        return Decision(config.UNIT_PET, ATYPE, tgt, config.SKILL_FIRE)
    # Danh thuong -> cung rule target nhu Hoa Tien
    tgt = _aoe_target(state.enemy_slots, offered) or (offered[0] if offered else 1)
    return Decision(config.UNIT_PET, ATYPE, tgt, config.SKILL_NORMAL)
