"""Logic AI combat - quyet dinh skill + target moi luot.

atype=1 (gia tri server chap nhan cho bot; atype 2/3 bi da khoi tran).
Quy tac skill:
  CHAR (unit 3): SP>=100 -> Hoa Tien (AOE 3 hang ngang); ally HP<=60% -> Toan Tri Lieu; con lai -> danh thuong
  PET  (unit 2): SP>=15 -> Hoa Tien; con lai -> danh thuong

RULE TARGET (dung CHUNG cho danh thuong + combo -> moi unit dong target, combo moi an):
  1. Block 3 quai lien nhau cung hang (dau tien) -> con GIUA (AoE trung ca 3)
  2. Khong co -> block 2 quai (dau tien) -> con DAU
  3. Khong co -> con LE dau tien
(KHONG dung focus lowest-HP nua vi moi unit ra target khac nhau -> vo combo.)
"""
import threading, time
from . import config

# --- Dieu phoi HEAL: ca party chi 1 unit heal/luot, chon con SP CAO NHAT ---
# bot_standalone chay moi nick trong cung 1 process (thread) -> chia se bien nay.
# Co che: unit muon heal -> DANG KY (key, SP) -> cho HEAL_BARRIER giay cho cac con khac
# dang ky -> chi con SP CAO NHAT moi heal, con lai danh quai. Tranh thua heal thieu dame.
_heal_lock = threading.Lock()
_heal_pool = {}          # key -> (sp, ts) ung vien heal
_heal_done = {"t": 0.0}  # thoi diem heal gan nhat (ca party)
HEAL_BARRIER = 0.4       # giay cho cac unit khac dang ky truoc khi chon
HEAL_COOLDOWN = 2.5      # giay: trong cua so nay chi 1 unit heal


def _heal_decide(key, sp):
    """Dang ky ung vien heal, cho barrier, tra ve True neu minh la SP cao nhat + gianh quyen."""
    now = time.time()
    with _heal_lock:
        if now - _heal_done["t"] < HEAL_COOLDOWN:
            return False                 # da co nguoi heal turn nay
        _heal_pool[key] = (sp, now)
    time.sleep(HEAL_BARRIER)             # cho cac unit khac trong party dang ky
    with _heal_lock:
        if time.time() - _heal_done["t"] < HEAL_COOLDOWN:
            return False                 # ai do da heal trong luc cho
        recent = {k: v for k, v in _heal_pool.items() if now - v[1] <= HEAL_BARRIER + 1.0}
        # con SP cao nhat (tie-break: key) -> winner
        winner = max(recent, key=lambda k: (recent[k][0], k))
        if winner == key:
            _heal_done["t"] = time.time()
            return True
        return False


# atype = VI TRI FORMATION cua member (leader o giua). Tinh tu roster, luu o state.my_atype.
# vd: 2 member + leader -> member1=vi tri 1 (atype1), leader=2, member2=vi tri 3 (atype3).
# Sai atype = bi server da (slot strict).


class Decision:
    # b = loai dich cua skill: 0=danh quai, 2=1 dong doi, 3=toan party (tu defend_test.pcap)
    def __init__(self, unit, atype, target, skill, b=0):
        self.unit = unit
        self.atype = atype
        self.target = target
        self.skill = skill
        self.b = b

    def __repr__(self):
        return f"Decision(unit={self.unit} atype={self.atype} b={self.b} target={self.target} skill={self.skill})"


def _offered_targets(options, atype):
    """Cac target hop le cho atype dang dung (server liet ke trong 0x35)."""
    t = [o[1] for o in options if o[0] == atype]
    return t or [o[1] for o in options]


# Vi tri quai noi bo: pos = hang*10 + cot. hang(b byte)=pos//10, cot(target)=pos%10.
def _row(pos):
    return pos // 10


def _col(pos):
    return pos % 10


def _same_row(a, b):
    """Cung hang battle? (2 hang: pos//10 = 0 hang truoc, 1 hang sau)."""
    return a // 10 == b // 10


def _train_target(enemy_slots, offered):
    """RULE TARGET KHI TRAIN (dung CHUNG cho danh thuong + combo -> moi unit dong target,
    combo moi an). 'offered' = danh sach COT hop le (0x35). Tra ve pos (hang*10+cot).
      1. Block 3 quai lien nhau cung hang (DAU TIEN) -> con GIUA (AoE trung ca 3)
      2. Khong co -> block 2 quai (DAU TIEN) -> con DAU (thap nhat)
      3. Khong co -> con LE dau tien (thap nhat)
    """
    off = set(offered)
    es = set(enemy_slots)
    if not es:
        return None
    s = sorted(es)
    for a in s:   # nhom 3 cung hang -> con giua (cot phai offered)
        if (a + 1) in es and (a + 2) in es and _same_row(a, a + 2) and _col(a + 1) in off:
            return a + 1
    for a in s:   # nhom 2 cung hang -> con thap nhat
        if (a + 1) in es and _same_row(a, a + 1):
            if _col(a) in off:
                return a
            if _col(a + 1) in off:
                return a + 1
    for t in s:   # le -> con thap nhat co cot offered
        if _col(t) in off:
            return t
    return None


def _attack(unit, atype, pos, skill, fb_col):
    """Tao Decision tan cong: pos -> b=hang(pos//10), target=cot(pos%10).
    pos None -> fallback cot fb_col (hang truoc, b=0)."""
    if pos is None:
        return Decision(unit, atype, fb_col, skill, b=0)
    return Decision(unit, atype, _col(pos), skill, b=_row(pos))


def _has_group3(enemy_slots):
    """Co 3 con quai lien nhau cung hang khong (de Hoa Tien dang dong SP)."""
    es = set(enemy_slots)
    for a in sorted(es):
        if (a + 1) in es and (a + 2) in es and _same_row(a, a + 2):
            return True
    return False


def _has_group2(enemy_slots):
    """Co >=2 con quai lien nhau cung hang khong (Hoa Tien trung >=2 con)."""
    es = set(enemy_slots)
    for a in sorted(es):
        if (a + 1) in es and _same_row(a, a + 1):
            return True
    return False


def pick_combo_skill(skills):
    """Tu set skill cua unit, chon skill COMBO TRAINING dau tien (uu tien). None neu khong co.
    Dung chung cho char (skill tu 0x28) va pet (skill tu pets.json)."""
    for s in getattr(config, "COMBO_TRAIN_SKILLS", []):
        if s in skills:
            return s
    return None


def _skill_cost(skill):
    """SP cost cua skill (0 neu chua biet)."""
    return getattr(config, "SKILL_SP_COST", {}).get(skill, 0)


def decide_char(state, options, first_turn=False):
    at = state.my_atype
    offered = _offered_targets(options, at)
    fb = offered[0] if offered else 1
    # 1) HOI MAU: co thanh vien HP yeu + du SP + co skill heal + la con SP cao nhat duoc heal
    if (state.any_ally_low(config.HEAL_HP_THRESHOLD)
            and state.char.sp >= config.HEAL_SP_COST
            and config.SKILL_HEAL_ALL in state.skills_char
            and _heal_decide(state.label + ":char", state.char.sp)):
        return Decision(config.UNIT_CHAR, at, at, config.SKILL_HEAL_ALL, b=3)
    # 2) COMBO: char co skill combo + du SP (>=reserve VA >=cost skill) + >=2 quai lien nhau
    combo = pick_combo_skill(state.skills_char)
    if (combo and state.char.sp >= max(config.CHAR_FIRE_MIN_SP, _skill_cost(combo))
            and _has_group2(state.enemy_slots)):
        return _attack(config.UNIT_CHAR, at, _train_target(state.enemy_slots, offered), combo, fb)
    # 3) Danh thuong - DUNG CHUNG rule target (de combo + dong target voi pet/member)
    return _attack(config.UNIT_CHAR, at, _train_target(state.enemy_slots, offered), config.SKILL_NORMAL, fb)


def decide_pet(state, options, first_turn=False):
    at = state.my_atype
    offered = _offered_targets(options, at)
    fb = offered[0] if offered else 1
    # 1) HOI MAU: pet co skill heal (tu pets.json) + dong doi yeu + du SP + la con SP cao nhat
    if (state.any_ally_low(config.HEAL_HP_THRESHOLD)
            and state.pet.sp >= config.HEAL_SP_COST
            and config.SKILL_HEAL_ALL in state.pet_skills
            and _heal_decide(state.label + ":pet", state.pet.sp)):
        return Decision(config.UNIT_PET, at, at, config.SKILL_HEAL_ALL, b=3)
    # 2) COMBO: pet co skill combo (tu pets.json) + du SP (>=cost skill) + >=2 quai lien nhau
    combo = pick_combo_skill(state.pet_skills)
    if (combo and state.pet.sp >= max(config.PET_FIRE_MIN_SP, _skill_cost(combo))
            and _has_group2(state.enemy_slots)):
        return _attack(config.UNIT_PET, at, _train_target(state.enemy_slots, offered), combo, fb)
    # Danh thuong - DUNG CHUNG rule target (de combo + dong target voi char/member)
    return _attack(config.UNIT_PET, at, _train_target(state.enemy_slots, offered), config.SKILL_NORMAL, fb)
