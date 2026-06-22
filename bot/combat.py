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


# --- HOI SINH: dieu phoi giong heal (1 con hoi sinh/luot, con SP cao nhat) + registry skill ---
_revive_lock = threading.Lock()
_revive_pool = {}            # key -> (sp, ts)
_revive_done = {"t": 0.0}
_revive_reg = {}             # (party_idx, b1, slot) -> True: o vi tri do co skill hoi sinh
REVIVE_BARRIER = 0.4
REVIVE_COOLDOWN = 2.5


def register_revive(party_idx, b1, slot):
    """Dang ky: party_idx, b1(3=char/2=pet), slot CO skill hoi sinh -> de chon target con chet
    co revive skill TRUOC (uu tien hoi sinh nguoi biet hoi sinh, ho lai cuu nguoi khac)."""
    _revive_reg[(party_idx, b1, slot)] = True


def _slot_has_revive(party_idx, b1, slot):
    return _revive_reg.get((party_idx, b1, slot), False)


def _revive_decide(key, sp):
    """Giong _heal_decide: con SP cao nhat trong cac ung vien hoi sinh -> gianh quyen luot nay."""
    now = time.time()
    with _revive_lock:
        if now - _revive_done["t"] < REVIVE_COOLDOWN:
            return False
        _revive_pool[key] = (sp, now)
    time.sleep(REVIVE_BARRIER)
    with _revive_lock:
        if time.time() - _revive_done["t"] < REVIVE_COOLDOWN:
            return False
        recent = {k: v for k, v in _revive_pool.items() if now - v[1] <= REVIVE_BARRIER + 1.0}
        winner = max(recent, key=lambda k: (recent[k][0], k))
        if winner == key:
            _revive_done["t"] = time.time()
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


# ---- Tra cuu thuoc tinh skill tu config.SKILL_INFO (auto tu skills_data.json: cost/combo/splash).
#      Thieu data -> fallback (SKILL_SP_COST / coi nhu combo duoc) de khong vo combat. ----
def _sinfo(skill):
    return getattr(config, "SKILL_INFO", {}).get(skill)


def _skill_cost(skill):
    """SP cost cua skill (tu SKILL_INFO; fallback SKILL_SP_COST; 0 neu chua biet)."""
    info = _sinfo(skill)
    if info is not None:
        return info.get("cost", 0)
    return getattr(config, "SKILL_SP_COST", {}).get(skill, 0)


def _cat(skill):
    """LOAI skill (idx11): 1=dame combo duoc, 2=dame khong combo, 4..15=support. Thieu -> 1."""
    info = _sinfo(skill)
    return info.get("cat", 1) if info is not None else 1


def _is_attack(skill):
    """True = skill GAY DAME (cat in {1,2}). False = support (heal/buff/giai/hoi sinh...)."""
    return _cat(skill) in (1, 2)


def _can_combo(skill):
    """True = skill COMBO DUOC (cat==1: HoaTien/NemDa/LoanKich/DaLan). False = khong combo
    (dame cat=2 nhu MuaDa/all-target, hoac support)."""
    return _cat(skill) == 1


def _splash(skill):
    """Kieu nham: 1=don, 2=trai doc, 3=trai ngang, 4=don dap (multi-hit 1 con), 8=TOAN BO quai."""
    info = _sinfo(skill)
    return info.get("splash", 1) if info is not None else 1


def _is_alltarget(skill):
    """True = skill DAME danh TOAN BO quai (splash==8: LieuNguyenHoa, LongTroiLoDat)."""
    return _is_attack(skill) and _splash(skill) == 8


def _is_revive(skill):
    """True = skill HOI SINH (cat==8: 'Hoi Sinh' 11013)."""
    return _cat(skill) == 8


def _try_revive(state, unit, skills, stat, options):
    """HOI SINH (check TRUOC heal): caster CON SONG + co skill hoi sinh + du SP + co dong doi CHET
    + thang dieu phoi (con SP cao nhat trong party hoi sinh). Target con chet uu tien:
      1) con chet CO skill hoi sinh (cuu nguoi biet cuu truoc) 2) maxHP goc cao nhat.
    Con chet thi KHONG cast (caster phai song). Tra Decision hoac None."""
    rev = next((s for s in skills if _is_revive(s)), None)
    if rev is None:
        return None
    if stat.hp_max > 0 and stat.hp <= 0:      # caster da chet -> ko cast
        return None
    if stat.sp < _skill_cost(rev):
        return None
    dead = state.dead_allies()                # [(b1,b2,hp_max)]
    if not dead:
        return None
    # dang ky chinh minh CO revive (de party biet vi tri minh la nguoi cuu duoc)
    pidx = getattr(state, "party_idx", None)
    if state.self_slot is not None:
        register_revive(pidx, 3 if unit == config.UNIT_CHAR else 2, state.self_slot)
    if not _revive_decide(state.label + (":char" if unit == config.UNIT_CHAR else ":pet"), stat.sp):
        return None
    # target: con chet co revive skill TRUOC -> roi maxHP cao nhat
    dead.sort(key=lambda x: (not _slot_has_revive(pidx, x[0], x[1]), -x[2]))
    b1, b2, _hp = dead[0]
    at = state.my_atype
    return Decision(unit, at, b2, rev, b=b1)   # target=slot con chet, b=loai con chet (3char/2pet)


def _combo_block_ok(combo, enemy_slots):
    """Du block quai de XAI skill combo nay chua?
      - splash=4 (don dap, DAT SP nhu Loan Kich) -> chi xai khi block 3 (2 quai -> phi).
      - splash 2/3 (trai, RE) -> block 2 la du."""
    need3 = _splash(combo) == 4
    return _has_group3(enemy_slots) if need3 else _has_group2(enemy_slots)


def pick_combo_skill(skills):
    """COMBO TRAIN: skill COMBO DUOC (cat==1) + splash 2/3/4 (don dap/trai), RE nhat. None neu khong.
    (Bo splash=1 don - phi SP danh combo 1 con.) Fallback COMBO_TRAIN_SKILLS neu thieu SKILL_INFO."""
    aoe = [s for s in skills if _can_combo(s) and _splash(s) in (2, 3, 4)]
    if aoe:
        return min(aoe, key=_skill_cost)
    for s in getattr(config, "COMBO_TRAIN_SKILLS", []):   # fallback khi chua co skills_data
        if s in skills:
            return s
    return None


def pick_boss_skill(skills):
    """Skill danh BOSS/don le: DAME (cat in {1,2}), uu tien splash 4 (don dap) > 1 (don), cung hang
    -> cost cao nhat. KHONG can combo. Khong co don dap/don -> skill DAU (skill[0], luon dame).
    skills phai co THU TU (list) de fallback skill[0] dung."""
    RANK = {4: 2, 1: 1}
    cand = [s for s in skills if _is_attack(s) and _splash(s) in (4, 1)]
    if cand:
        return max(cand, key=lambda s: (RANK[_splash(s)], _skill_cost(s)))
    lst = list(skills)
    return lst[0] if lst else None


def pick_alltarget_skill(skills):
    """Skill DAME danh TOAN BO quai (splash==8). RE nhat neu nhieu. None neu pet khong co."""
    allt = [s for s in skills if _is_alltarget(s)]
    return min(allt, key=_skill_cost) if allt else None


def _lowest_hp_enemy(state, offered):
    """Pos quai con SONG it mau NHAT (cot phai trong offered). None neu khong co.
    Dung khi danh boss/don le (quest <=5) - dam con sap chet truoc."""
    off = set(offered)
    alive = [(pos, hp) for pos, hp in state.enemy_hp.items() if hp > 0 and _col(pos) in off]
    if not alive:
        return None
    return min(alive, key=lambda x: x[1])[0]


def _combat_attack(state, unit, skills, stat, options, spam_attr, fire_min):
    """Quyet dinh TAN CONG (sau khi da loai heal) - DUNG CHUNG char + pet. 3 che do:
      BOSS  (boss_mode, dungeon): nuke = pick_boss_skill (don dap>don>skill dau), target it mau nhat.
      QUEST (quest_mode, start >5 quai):
            > 5 quai con  -> all-target (neu co) -> ko thi combo AoE -> danh thuong
            <=5 quai con  -> nhu boss + target IT MAU NHAT
      TRAIN (mac dinh): combo (AoE re, combo duoc) khi du SP+block (hoac spam SP day), ko thi danh thuong.
    SP thieu cho skill manh -> danh thuong, cho quan su hoi SP."""
    at = state.my_atype
    offered = _offered_targets(options, at)
    fb = offered[0] if offered else 1
    sp = stat.sp
    es = state.enemy_slots
    cost = _skill_cost

    def low_or_train():
        p = _lowest_hp_enemy(state, offered)
        return p if p is not None else _train_target(es, offered)

    # 1) BOSS mode
    if getattr(state, "boss_mode", False) and es:
        boss = pick_boss_skill(skills)
        pos = low_or_train()
        sk = boss if (boss and sp >= cost(boss)) else config.SKILL_NORMAL
        return _attack(unit, at, pos, sk, fb)

    # 2) QUEST mode (start >5 quai)
    if getattr(state, "quest_mode", False) and es:
        if len(es) > 5:
            allt = pick_alltarget_skill(skills)
            if allt and sp >= cost(allt):
                return _attack(unit, at, _train_target(es, offered), allt, fb)
            combo = pick_combo_skill(skills)   # ko co all-target -> combo AoE thuong
            if combo and sp >= max(fire_min, cost(combo)) and _combo_block_ok(combo, es):
                return _attack(unit, at, _train_target(es, offered), combo, fb)
            return _attack(unit, at, _train_target(es, offered), config.SKILL_NORMAL, fb)
        # <=5 quai -> nhu boss + target it mau nhat
        boss = pick_boss_skill(skills)
        pos = low_or_train()
        sk = boss if (boss and sp >= cost(boss)) else config.SKILL_NORMAL
        return _attack(unit, at, pos, sk, fb)

    # 3) TRAIN mode (combo)
    if stat.sp_max > 0 and sp >= stat.sp_max:
        setattr(state, spam_attr, True)
    combo = pick_combo_skill(skills)
    if (combo and sp >= max(fire_min, cost(combo))
            and (getattr(state, spam_attr) or _combo_block_ok(combo, es))):
        return _attack(unit, at, _train_target(es, offered), combo, fb)
    return _attack(unit, at, _train_target(es, offered), config.SKILL_NORMAL, fb)


def decide_char(state, options, first_turn=False):
    at = state.my_atype
    # HOI SINH (truoc heal): co dong doi chet + char co skill hoi sinh + thang dieu phoi
    rv = _try_revive(state, config.UNIT_CHAR, state.skills_char, state.char, options)
    if rv is not None:
        return rv
    # HOI MAU: thanh vien HP yeu + du SP + co skill heal + la con SP cao nhat duoc heal
    if (state.any_ally_low(config.HEAL_HP_THRESHOLD)
            and state.char.sp >= config.HEAL_SP_COST
            and config.SKILL_HEAL_ALL in state.skills_char
            and _heal_decide(state.label + ":char", state.char.sp)):
        _low = state.lowest_hp_ally()
        _ht = _low.slot if (_low is not None and getattr(_low, "slot", None) is not None) else at
        return Decision(config.UNIT_CHAR, at, _ht, config.SKILL_HEAL_ALL, b=3)
    return _combat_attack(state, config.UNIT_CHAR, state.skills_char, state.char, options,
                          "char_spam", config.CHAR_FIRE_MIN_SP)


def decide_pet(state, options, first_turn=False):
    at = state.my_atype
    # HOI SINH (truoc heal): co dong doi chet + pet co skill hoi sinh + thang dieu phoi
    rv = _try_revive(state, config.UNIT_PET, state.pet_skills, state.pet, options)
    if rv is not None:
        return rv
    # HOI MAU: pet co skill heal + dong doi yeu + du SP + la con SP cao nhat
    if (state.any_ally_low(config.HEAL_HP_THRESHOLD)
            and state.pet.sp >= config.HEAL_SP_COST
            and config.SKILL_HEAL_ALL in state.pet_skills
            and _heal_decide(state.label + ":pet", state.pet.sp)):
        _low = state.lowest_hp_ally()
        _ht = _low.slot if (_low is not None and getattr(_low, "slot", None) is not None) else at
        return Decision(config.UNIT_PET, at, _ht, config.SKILL_HEAL_ALL, b=3)
    return _combat_attack(state, config.UNIT_PET, state.pet_skills, state.pet, options,
                          "pet_spam", config.PET_FIRE_MIN_SP)
