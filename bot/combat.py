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
        tgt = _aoe_target(state.enemy_slots, offered) or fb
        return Decision(config.UNIT_CHAR, at, tgt, combo)
    # 3) Danh thuong - chon target nham cum quai (combo)
    tgt = _aoe_target(state.enemy_slots, offered) or fb
    return Decision(config.UNIT_CHAR, at, tgt, config.SKILL_NORMAL)


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
        tgt = _aoe_target(state.enemy_slots, offered) or fb
        return Decision(config.UNIT_PET, at, tgt, combo)
    # Danh thuong - chon target giong Hoa Tien/Nem Da (nham cum quai)
    tgt = _aoe_target(state.enemy_slots, offered) or fb
    return Decision(config.UNIT_PET, at, tgt, config.SKILL_NORMAL)
