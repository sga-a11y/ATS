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
import threading, time, logging
from . import config

log = logging.getLogger("bot")

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


# --- HOI SP TOAN TEAM (Toan Hoi Ma): dieu phoi giong heal - 1 con cast/luot, con SP cao nhat ---
_spr_lock = threading.Lock()
_spr_pool = {}
_spr_done = {"t": 0.0}
SPR_BARRIER = 0.4
SPR_COOLDOWN = 2.5


def _sprestore_decide(key, sp):
    """Giong _heal_decide: trong cac unit CO skill hoi SP + thay dong doi thieu SP, con SP cao nhat
    gianh quyen cast luot nay (chi 1 con cast la du)."""
    now = time.time()
    with _spr_lock:
        if now - _spr_done["t"] < SPR_COOLDOWN:
            return False
        _spr_pool[key] = (sp, now)
    time.sleep(SPR_BARRIER)
    with _spr_lock:
        if time.time() - _spr_done["t"] < SPR_COOLDOWN:
            return False
        recent = {k: v for k, v in _spr_pool.items() if now - v[1] <= SPR_BARRIER + 1.0}
        winner = max(recent, key=lambda k: (recent[k][0], k))
        if winner == key:
            _spr_done["t"] = time.time()
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
    """Cac target hop le cho atype dang dung (server liet ke trong 0x35).
    KHONG FALLBACK sang target cua atype KHAC: server gui 1 goi 0x35 RIENG cho tung unit (party 5
    nguoi = toi 10 goi/luot, moi goi CHI 1 atype) -> bot nhan duoc goi 0x35 cua THANH VIEN KHAC (chua
    phai luot minh) VAN kich _arm_decision (khong loc theo atype o tang goi). Truoc day fallback
    'options rong cho atype minh -> dung target cua nguoi khac' -> gui atk SAI LUC/SAI DU LIEU (server
    im lang bo qua -> turn khong tien -> lap lai Y HET vi enemy_hp chua doi). Rong -> [] (KHONG danh,
    _make_decisions se bo qua cycle nay, cho goi 0x35 That cua minh)."""
    return [o[1] for o in options if o[0] == atype]


# Vi tri quai noi bo: pos = hang*10 + cot. hang(b byte)=pos//10, cot(target)=pos%10.
def _row(pos):
    return pos // 10


def _col(pos):
    return pos % 10


def _same_row(a, b):
    """Cung hang battle? (2 hang: pos//10 = 0 hang truoc, 1 hang sau)."""
    return a // 10 == b // 10


def _offer_min(offered):
    """Goc index cua cot trong 0x35 offer: TRAIN bat dau tu 0 (-> +0), PHO BAN TO DOI bat dau tu 1
    (-> +1). cot noi bo (b2) LUON 0-indexed -> target_gui = b2 + offer_min. Tu dieu chinh, an toan
    cho ca train (min=0 = khong doi) lan pho ban (min=1 = +1)."""
    return min(offered) if offered else 0


def _train_target(enemy_slots, offered):
    """RULE TARGET KHI TRAIN (dung CHUNG cho danh thuong + combo -> moi unit dong target,
    combo moi an). 'offered' = danh sach COT hop le (0x35, theo offer-space). Tra ve pos (hang*10+cot).
      1. Block 3 quai lien nhau cung hang (DAU TIEN) -> con GIUA (AoE trung ca 3)
      2. Khong co -> block 2 quai (DAU TIEN) -> con DAU (thap nhat)
      3. Khong co -> con LE dau tien (thap nhat)
    So sanh cot: b2 (0-indexed) + offer_min phai nam trong offered (xem _offer_min)."""
    off = set(offered)
    om = _offer_min(offered)
    es = set(enemy_slots)
    if not es:
        return None
    s = sorted(es)
    for a in s:   # nhom 3 cung hang
        if (a + 1) in es and (a + 2) in es and _same_row(a, a + 2):
            # Uu tien con GIUA (AoE trung ca 3) NEU cot no offered. Cot giua KHONG offered (atype
            # nay khong voi toi giua) -> FALLBACK NGAY trong CUNG khoi 3 nay (uu tien DAU truoc,
            # roi CUOI) - TRUOC DAY roi thang xuong vong quet "nhom 2" o duoi, vo tinh khop cap
            # (a+1,a+2) truoc cap (a,a+1) o LAN QUET SAU -> ra con CUOI (thu 3) thay vi con DAU,
            # sai voi ky vong "gan nhat voi giua" (da xac nhan qua quan sat thuc te: 3 con gan
            # nhau nhung bi target con thu 3 thay vi giua).
            if (_col(a + 1) + om) in off:
                return a + 1
            if (_col(a) + om) in off:
                return a
            if (_col(a + 2) + om) in off:
                return a + 2
    for a in s:   # nhom 2 cung hang -> con thap nhat
        if (a + 1) in es and _same_row(a, a + 1):
            if (_col(a) + om) in off:
                return a
            if (_col(a + 1) + om) in off:
                return a + 1
    for t in s:   # le -> con thap nhat co cot offered
        if (_col(t) + om) in off:
            return t
    return None


def _attack(unit, atype, pos, skill, fb_col, offered=None):
    """Tao Decision tan cong: pos -> b=hang(pos//10), target=cot(pos%10)+offer_min.
    pos None -> fallback cot fb_col (da o offer-space, hang truoc, b=0)."""
    if pos is None:
        return Decision(unit, atype, fb_col, skill, b=0)
    return Decision(unit, atype, _col(pos) + _offer_min(offered), skill, b=_row(pos))


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


def pick_sp_restore_skill(skills):
    """Skill HOI SP TOAN TEAM (Toan Hoi Ma = cat 6). Lay cat-6 COST CAO NHAT (ban team dat hon ban
    don, vd 0x2b01/40 > 0x2afe/35). None neu unit khong co."""
    cand = [s for s in skills if (_sinfo(s) or {}).get("cat") == 6]
    return max(cand, key=_skill_cost) if cand else None


def _try_sp_restore(state, unit, skills, stat):
    """HOI SP TOAN TEAM - CHI quest_mode, goi SAU heal HP / TRUOC attack:
      - unit co skill cat-6 (Toan Hoi Ma) + ban than du SP (>=cost)
      - co dong doi (TRU chinh minh) SP < 50%  (doc tu state.allies, SP ca party co trong 0x33)
      - la unit SP cao nhat trong nhom co skill (_sprestore_decide dieu phoi, 1 con cast la du)
    Target = slot dong doi <50%, b=3 (skill team). Tra Decision hoac None."""
    spr = pick_sp_restore_skill(skills)
    if spr is None:
        return None
    if not getattr(state, "quest_mode", False) or state.self_slot is None:
        return None
    if stat.sp < _skill_cost(spr):
        return None
    b1 = 3 if unit == config.UNIT_CHAR else 2
    low_slot = state.ally_low_sp(getattr(config, "SP_RESTORE_THRESHOLD", 0.5), (b1, state.self_slot))
    if low_slot is None:
        return None
    key = state.label + (":char" if unit == config.UNIT_CHAR else ":pet") + ":spr"
    if not _sprestore_decide(key, stat.sp):
        return None
    return Decision(unit, state.my_atype, low_slot, spr, b=3)


def _lowest_hp_enemy(state, offered):
    """Pos quai con SONG it mau NHAT (cot phai trong offered). None neu khong co.
    Dung khi danh boss/don le (quest <=5) - dam con sap chet truoc."""
    off = set(offered)
    om = _offer_min(offered)
    alive = [(pos, hp) for pos, hp in state.enemy_hp.items() if hp > 0 and (_col(pos) + om) in off]
    if not alive:
        return None
    return min(alive, key=lambda x: x[1])[0]


def _anti_stall(state, unit, pos, skill, es, offered):
    """Chong ket cung: neu 3 lan LIEN TIEP cua unit nay ra CUNG (pos, skill) MA enemy_hp[pos]
    KHONG DOI (danh khong an, hoac goi bi server bo qua vi ly do khac) -> DOI (target khac con
    song neu co, hoac doi skill neu chi con 1 con) de dam bao goi 0x32 KHAC NOI DUNG so lan truoc.
    Da xac nhan qua thuc te: co truong hop 1 quai HP thap (vd 36) bi 5 acc nhac lien tuc CUNG
    skill+target hang chuc lan/2 phut ma HP dung yen tuyet doi -> nghi server tu drop request
    lap noi dung (du tail 0x32 co random) -> can chu dong doi noi dung de thoat vong lap."""
    key_attr = "_stall_char" if unit == config.UNIT_CHAR else "_stall_pet"
    hp_now = state.enemy_hp.get(pos)
    prev = getattr(state, key_attr, None)   # (pos, skill, hp, streak)
    if prev is not None and prev[0] == pos and prev[1] == skill and prev[2] == hp_now:
        streak = prev[3] + 1
    else:
        streak = 0
    if streak >= 2:   # day la lan thu 3 LIEN TIEP y het -> doi
        alive = [p for p, hp in state.enemy_hp.items() if hp > 0 and p != pos]
        if alive:
            new_pos = min(alive)   # con khac (khong quan tam HP - uu tien PHA VO LAP hon la toi uu)
            log.warning("[%s] ANTI-STALL: %s lap %d lan cung pos=%d skill=%d ma HP khong doi -> "
                        "doi target sang pos=%d", state.label, "CHAR" if unit == config.UNIT_CHAR else "PET",
                        streak + 1, pos, skill, new_pos)
            setattr(state, key_attr, (new_pos, skill, state.enemy_hp.get(new_pos), 0))
            return new_pos, skill
        # chi 1 con song -> doi skill (thuong <-> skill khac neu co) thay vi doi target
        alt_skill = config.SKILL_NORMAL if skill != config.SKILL_NORMAL else skill
        if alt_skill == skill:
            cand = [s for s in skills if s != skill]
            alt_skill = cand[0] if cand else skill
        log.warning("[%s] ANTI-STALL: %s lap %d lan cung pos=%d skill=%d ma HP khong doi (chi 1 con "
                    "song) -> doi skill sang %d", state.label, "CHAR" if unit == config.UNIT_CHAR else "PET",
                    streak + 1, pos, skill, alt_skill)
        setattr(state, key_attr, (pos, alt_skill, hp_now, 0))
        return pos, alt_skill
    setattr(state, key_attr, (pos, skill, hp_now, streak))
    return pos, skill


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
    # CHI danh khi CO du lieu quai MOI (goi 0x33 that) ke tu lan danh truoc. Goi 0x35 (offer luot)
    # KHONG mang du lieu quai -> neu 0x35 den ma KHONG co 0x33 moi kem theo (vd tran DA KET THAT
    # nhung con offer "tan du" den tre, hoac server chi re-broadcast lai cung turn) -> danh LAI tren
    # trang thai CU (stale) la SAI - co the tran da xong that roi. User quan sat truc tiep: end battle
    # -> van gui atk. Skip (None) neu enemy_gen KHONG doi so voi lan danh truoc cua UNIT nay.
    gen_attr = "last_atk_gen_char" if unit == config.UNIT_CHAR else "last_atk_gen_pet"
    if getattr(state, gen_attr, -1) == state.enemy_gen:
        return None
    setattr(state, gen_attr, state.enemy_gen)
    if not es:
        # KHONG CON QUAI SONG (da chet het) -> KHONG danh (nhanh TRAIN ben duoi khong check es rong,
        # se fallback danh MU cot 1 -> goi 0x32 thua sau khi tran DA KET THUC that (server gui them
        # 1 goi 0x35 "tan du" sau khi thang). User xac nhan qua quan sat truc tiep man hinh: end
        # battle -> bot van gui atk 1 lan nua. Return None -> _make_decisions bo qua, khong gui gi.
        return None

    def low_or_train():
        p = _lowest_hp_enemy(state, offered)
        return p if p is not None else _train_target(es, offered)

    # 1) BOSS mode
    if getattr(state, "boss_mode", False) and es:
        boss = pick_boss_skill(skills)
        pos = low_or_train()
        sk = boss if (boss and sp >= cost(boss)) else config.SKILL_NORMAL
        pos, sk = _anti_stall(state, unit, pos, sk, es, offered)
        return _attack(unit, at, pos, sk, fb, offered)

    # 2) QUEST mode (start >5 quai)
    if getattr(state, "quest_mode", False) and es:
        if len(es) > 5:
            allt = pick_alltarget_skill(skills)
            if allt and sp >= cost(allt):
                return _attack(unit, at, _train_target(es, offered), allt, fb, offered)
            combo = pick_combo_skill(skills)   # ko co all-target -> combo AoE thuong
            if combo and sp >= max(fire_min, cost(combo)) and _combo_block_ok(combo, es):
                return _attack(unit, at, _train_target(es, offered), combo, fb, offered)
            return _attack(unit, at, _train_target(es, offered), config.SKILL_NORMAL, fb, offered)
        # <=5 quai -> nhu boss + target it mau nhat
        boss = pick_boss_skill(skills)
        pos = low_or_train()
        sk = boss if (boss and sp >= cost(boss)) else config.SKILL_NORMAL
        pos, sk = _anti_stall(state, unit, pos, sk, es, offered)
        return _attack(unit, at, pos, sk, fb, offered)

    # 3) TRAIN mode (combo)
    if stat.sp_max > 0 and sp >= stat.sp_max:
        setattr(state, spam_attr, True)
    combo = pick_combo_skill(skills)
    if (combo and sp >= max(fire_min, cost(combo))
            and (getattr(state, spam_attr) or _combo_block_ok(combo, es))):
        return _attack(unit, at, _train_target(es, offered), combo, fb, offered)
    return _attack(unit, at, _train_target(es, offered), config.SKILL_NORMAL, fb, offered)


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
    # HOI SP TOAN TEAM (chi quest_mode): sau heal HP, truoc tan cong
    spr = _try_sp_restore(state, config.UNIT_CHAR, state.skills_char, state.char)
    if spr is not None:
        return spr
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
    # HOI SP TOAN TEAM (chi quest_mode): sau heal HP, truoc tan cong
    spr = _try_sp_restore(state, config.UNIT_PET, state.pet_skills, state.pet)
    if spr is not None:
        return spr
    return _combat_attack(state, config.UNIT_PET, state.pet_skills, state.pet, options,
                          "pet_spam", config.PET_FIRE_MIN_SP)
