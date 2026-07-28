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
import threading, time, logging, unicodedata
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


# Ten skill LOGIC (id 1xxxx dung trong Decision) - CHI de log cho de doc (thay vi soi id chay).
# Nguon: KNOWLEDGE.md bang skill + config.SKILL_SP_COST comments.
SKILL_NAMES = {
    10000: "Đánh thường",
    10005: "Ném Đá",
    11004: "Thanh Lưu",
    11009: "Hồi Sinh",
    11010: "Toàn Trị Liệu",
    12003: "Hỏa Tiễn",
    12006: "Nhất Kích",
    12009: "Hỏa Kiếm",
    13013: "Loạn Kích",
    17001: "Phòng thủ",
    17997: "Bỏ chạy",
    18001: "Bỏ chạy",
}


class Decision:
    # b = loai dich cua skill: 0=danh quai, 2=1 dong doi, 3=toan party (tu defend_test.pcap)
    def __init__(self, unit, atype, target, skill, b=0):
        self.unit = unit
        self.atype = atype
        self.target = target
        self.skill = skill
        self.b = b

    def __repr__(self):
        _sn = SKILL_NAMES.get(self.skill)
        _sk = f"{self.skill}({_sn})" if _sn else str(self.skill)
        return f"Decision(unit={self.unit} atype={self.atype} b={self.b} target={self.target} skill={_sk})"


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


def _col_reachable(col_val, off):
    """Cot 'col_val' (0-indexed noi bo) co NAM TRONG offered (server cho phep) khong - thu CA 2
    quy uoc (0-indexed thang, hoac +1 kieu pho ban to doi) THAY VI doan 1 offset chung cho ca tran
    (da xac nhan sai - xem _offer_min)."""
    return col_val in off or (col_val + 1) in off


def _resolve_target(pos, offered):
    """Target THAT gui cho server ung voi pos: uu tien cot dung y (0-indexed) neu no nam trong
    offered, khong thi thu +1 (quy uoc pho ban to doi). Tra None neu KHONG cot nao hop le (offered
    khong chua con nay - hiem, coi nhu khong the danh con do luc nay)."""
    c = _col(pos)
    off = set(offered)
    if c in off:
        return c
    if (c + 1) in off:
        return c + 1
    return None


def _train_target(enemy_slots, offered):
    """RULE TARGET KHI TRAIN (dung CHUNG cho danh thuong + combo -> moi unit dong target,
    combo moi an). 'offered' = danh sach COT hop le (0x35, theo offer-space). Tra ve pos (hang*10+cot).
      1. Block 3 quai lien nhau cung hang (DAU TIEN) -> con GIUA (AoE trung ca 3)
      2. Khong co -> block 2 quai (DAU TIEN) -> con DAU (thap nhat)
      3. Khong co -> con LE dau tien (thap nhat)
    So sanh cot: dung _col_reachable (kiem tra TUNG cot that, KHONG doan offset chung - xem
    _resolve_target/_offer_min)."""
    off = set(offered)
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
            if _col_reachable(_col(a + 1), off):
                return a + 1
            log.warning("TRAIN-TARGET: 3 con lien nhau (pos=%d,%d,%d) nhung COT GIUA (%d) KHONG "
                        "offered (off=%s) -> fallback DAU/CUOI. Can log nay de xac dinh day la "
                        "server THAT SU khong cho with toi giua (atype nay) hay bug o cho khac.",
                        a, a + 1, a + 2, _col(a + 1), sorted(off))
            if _col_reachable(_col(a), off):
                return a
            if _col_reachable(_col(a + 2), off):
                return a + 2
    for a in s:   # nhom 2 cung hang -> con thap nhat
        if (a + 1) in es and _same_row(a, a + 1):
            if _col_reachable(_col(a), off):
                return a
            if _col_reachable(_col(a + 1), off):
                return a + 1
    for t in s:   # le -> con thap nhat co cot offered
        if _col_reachable(_col(t), off):
            return t
    return None


def _attack(unit, atype, pos, skill, fb_col, offered=None):
    """Tao Decision tan cong: pos -> b=hang(pos//10), target=cot THAT (_resolve_target - kiem tra
    cot co nam trong offered KHONG, KHONG doan offset chung nhu _offer_min cu - da xac nhan sai:
    co truong hop offered=[1..5] ma KHONG can +1, lam target lech sang con ke ben con dinh danh).
    pos None -> fallback cot fb_col (da o offer-space, hang truoc, b=0)."""
    if pos is None:
        return Decision(unit, atype, fb_col, skill, b=0)
    t = _resolve_target(pos, offered) if offered else _col(pos)
    if t is None:   # cot that KHONG nam trong offered (hiem) -> fallback ve cot tho (con hon khong gui)
        t = _col(pos)
    return Decision(unit, atype, t, skill, b=_row(pos))


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


def _has_support_skill(skills):
    """Unit co it nhat 1 skill HOI: hoi sinh (cat8) / Toan Tri Lieu (11010) / Toan Hoi Ma (cat6).
    -> quest mode: de danh SP cho vai tro hoi, chi danh skill atk khi SP > SUPPORT_RESERVE_SP."""
    if any(_is_revive(s) for s in skills):
        return True
    if getattr(config, "SKILL_HEAL_ALL", None) in skills:
        return True
    return pick_sp_restore_skill(skills) is not None


def _revive_decision_for_skill(state, unit, stat, rev):
    """Dung skill hoi sinh cu the, target con chet tu dong theo rule uu tien chung."""
    if rev is None or not _is_revive(rev):
        return None
    # HET QUAI SONG = tran DA KET (server gui them 0x35 "tan du" sau khi thang) -> KHONG hoi sinh:
    # dong doi chet se TU song lai sau tran, cast luc nay chi phi luot + spam. Giong guard 'if not es'
    # ben _combat_attack (fix user quan sat: cuoi tran cu cast Hoi Sinh mai).
    if not getattr(state, "enemy_slots", None):
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


def _try_revive(state, unit, skills, stat, options):
    """HOI SINH (check TRUOC heal): caster CON SONG + co skill hoi sinh + du SP + co dong doi CHET
    + thang dieu phoi (con SP cao nhat trong party hoi sinh). Target con chet uu tien:
      1) con chet CO skill hoi sinh (cuu nguoi biet cuu truoc) 2) maxHP goc cao nhat.
    Con chet thi KHONG cast (caster phai song). Tra Decision hoac None."""
    rev = next((s for s in skills if _is_revive(s)), None)
    return _revive_decision_for_skill(state, unit, stat, rev)


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
    alive = [(pos, hp) for pos, hp in state.enemy_hp.items() if hp > 0 and _col_reachable(_col(pos), off)]
    if not alive:
        return None
    return min(alive, key=lambda x: x[1])[0]


_CUSTOM_AUTO = object()


def _battle_rules(state, unit_key):
    cfg = getattr(state, "battle_config", {}) or {}
    raw = cfg.get(unit_key)
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict) and r.get("enabled", True) is not False]
    if isinstance(raw, dict):   # tuong thich ban format tam thoi cu
        mode = raw.get("mode", "auto")
        skill = {"normal": "normal", "defend": "defend", "skill": raw.get("train_skill")}.get(mode, "auto")
        return [{"enabled": True, "condition": "always", "skill": skill or "auto", "target": raw.get("target", "auto")}]
    return []


def _compare_num(actual, op, expect):
    if op == "gt":
        return actual > expect
    if op == "lt":
        return actual < expect
    if op == "eq":
        return actual == expect
    if op == "lte":
        return actual <= expect
    return actual >= expect


def _caster_key(state, unit):
    if getattr(state, "self_slot", None) is None:
        return None
    return (3 if unit == config.UNIT_CHAR else 2), state.self_slot


def _any_ally_hp_below(state, pct, exclude=None):
    for key, u in getattr(state, "allies", {}).items():
        if exclude is not None and key == exclude:
            continue
        if u.hp_max > 0 and u.hp > 0 and (u.hp * 100 / u.hp_max) < pct:
            return True
    return False


def _any_ally_sp_below(state, pct, exclude=None):
    for key, u in getattr(state, "allies", {}).items():
        if exclude is not None and key == exclude:
            continue
        if u.hp <= 0:
            continue
        spmax = state.ally_spmax.get(key, getattr(u, "sp_max", 0))
        if spmax > 0 and (u.sp * 100 / spmax) < pct:
            return True
    return False


def _max_enemy_block(enemy_slots):
    rows = {}
    for pos in enemy_slots or []:
        rows.setdefault(_row(pos), []).append(_col(pos))
    best = 0
    for cols in rows.values():
        cur = 0
        prev = None
        for col in sorted(set(cols)):
            cur = cur + 1 if prev is not None and col == prev + 1 else 1
            best = max(best, cur)
            prev = col
    return best


def _is_mineral_battle(state):
    if getattr(state, "mineral_battle", False):
        return True
    for name in getattr(state, "enemy_names", ()) or ():
        s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii").lower()
        if s.startswith("khoang "):
            return True
    return False


def _rule_condition_ok(rule, state, stat, unit=None):
    cond = (rule or {}).get("condition", "always") if isinstance(rule, dict) else (rule or "always")
    cond = str(cond or "always")
    op = (rule or {}).get("op", "gte") if isinstance(rule, dict) else "gte"
    val = (rule or {}).get("value", None) if isinstance(rule, dict) else None
    n = len(getattr(state, "enemy_slots", []) or [])
    if cond == "always":
        return True
    if cond == "mineral":
        return _is_mineral_battle(state)
    # Tuong thich config cu: mob_gte_4 / hp_lte_50 / sp_gte_65...
    if cond.startswith("mob_gte_"):
        return n >= int(cond.rsplit("_", 1)[1])
    if cond.startswith("mob_lte_"):
        return n <= int(cond.rsplit("_", 1)[1])
    if cond.startswith("sp_gte_"):
        return stat.sp >= int(cond.rsplit("_", 1)[1])
    if cond.startswith("sp_lte_"):
        return stat.sp <= int(cond.rsplit("_", 1)[1])
    if cond == "sp_full":
        return stat.sp_max > 0 and stat.sp >= stat.sp_max
    if cond.startswith("hp_lte_"):
        return stat.hp_max > 0 and (stat.hp * 100 / stat.hp_max) <= int(cond.rsplit("_", 1)[1])
    if cond == "boss":
        return bool(getattr(state, "boss_mode", False))
    if cond == "quest":
        return bool(getattr(state, "quest_mode", False))
    if cond == "ally_dead":
        return bool(state.dead_allies())
    try:
        expect = int(val)
    except Exception:
        return False
    if cond == "mob":
        return _compare_num(n, op, expect)
    if cond == "block":
        return _compare_num(_max_enemy_block(getattr(state, "enemy_slots", []) or []), op, expect)
    if cond == "sp":
        return _compare_num(stat.sp, op, expect)
    if cond == "hp_pct":
        if stat.hp_max <= 0:
            return False
        return _compare_num((stat.hp * 100 / stat.hp_max), op, expect)
    if cond == "ally_hp_pct":
        return _any_ally_hp_below(state, expect, _caster_key(state, unit))
    if cond == "ally_sp_pct":
        return _any_ally_sp_below(state, expect, _caster_key(state, unit))
    return False


def _enemy_target_pos(state, offered, target_key):
    target_key = target_key or "auto"
    es = getattr(state, "enemy_slots", []) or []
    if not es:
        return None
    if target_key in ("auto", "block"):
        return _train_target(es, offered)
    alive = [(pos, hp) for pos, hp in state.enemy_hp.items()
             if hp > 0 and _col_reachable(_col(pos), set(offered))]
    if not alive:
        return None
    if target_key == "enemy_low_hp":
        return min(alive, key=lambda x: x[1])[0]
    if target_key == "enemy_high_hp":
        return max(alive, key=lambda x: x[1])[0]
    if target_key == "enemy_last":
        return max(alive, key=lambda x: x[0])[0]
    return min(alive, key=lambda x: x[0])[0]


def _ally_target(state, target_key, unit, atype):
    if target_key == "self":
        return (3 if unit == config.UNIT_CHAR else 2), atype
    cands = []
    for (b1, b2), u in getattr(state, "allies", {}).items():
        if u.hp_max <= 0 or u.hp <= 0:
            continue
        spmax = state.ally_spmax.get((b1, b2), getattr(u, "sp_max", 0))
        sppct = (u.sp / spmax) if spmax else 1.0
        cands.append((b1, b2, u.hp / u.hp_max, sppct))
    if not cands:
        return (3 if unit == config.UNIT_CHAR else 2), atype
    if target_key == "ally_high_hp":
        b1, b2, *_ = max(cands, key=lambda x: x[2])
    elif target_key == "ally_low_sp":
        b1, b2, *_ = min(cands, key=lambda x: x[3])
    elif target_key == "ally_high_sp":
        b1, b2, *_ = max(cands, key=lambda x: x[3])
    else:  # ally_low_hp
        b1, b2, *_ = min(cands, key=lambda x: x[2])
    return b1, b2


def _parse_rule_skill(value):
    if value in ("auto", "normal", "defend", "flee"):
        return value
    try:
        return int(value)
    except Exception:
        return "auto"


def _can_attack_new_enemy_gen(state, unit, atype=None):
    if unit == config.UNIT_PET and atype is not None and getattr(state, "solo_multipet", False):
        gen_map = state.last_atk_gen_multipet
        if gen_map.get(atype, -1) == state.enemy_gen:
            return False
        gen_map[atype] = state.enemy_gen
        return True
    gen_attr = "last_atk_gen_char" if unit == config.UNIT_CHAR else "last_atk_gen_pet"
    if getattr(state, gen_attr, -1) == state.enemy_gen:
        return False
    setattr(state, gen_attr, state.enemy_gen)
    return True


def _custom_decision(state, unit, unit_key, skills, stat, options, atype=None):
    rules = _battle_rules(state, unit_key)
    if not rules:
        return None
    at = state.my_atype if atype is None else atype
    offered = _offered_targets(options, at)
    fb = offered[0] if offered else 1
    learned = set(skills or [])
    for rule in rules:
        if not _rule_condition_ok(rule, state, stat, unit):
            continue
        skill = _parse_rule_skill(rule.get("skill", "auto"))
        target_key = rule.get("target", "auto")
        if skill == "auto":
            return _CUSTOM_AUTO
        if skill == "defend":
            return Decision(unit, at, at, config.SKILL_DEFEND, b=(3 if unit == config.UNIT_CHAR else 2))
        if skill == "flee":
            return Decision(unit, at, at, config.SKILL_FLEE, b=(3 if unit == config.UNIT_CHAR else 2))
        skill_id = config.SKILL_NORMAL if skill == "normal" else skill
        if isinstance(skill_id, int) and skill_id != config.SKILL_NORMAL:
            if skill_id not in learned:
                continue
            if stat.sp < _skill_cost(skill_id):
                continue
            if _is_revive(skill_id):
                rv = _revive_decision_for_skill(state, unit, stat, skill_id)
                if rv is not None:
                    return rv
                continue
        if target_key in ("ally_low_hp", "ally_high_hp", "ally_low_sp", "ally_high_sp", "self"):
            if isinstance(skill_id, int) and skill_id != config.SKILL_NORMAL:
                key = state.label + (":char" if unit == config.UNIT_CHAR else ":pet")
                if skill_id in (getattr(config, "SKILL_HEAL_ALL", None),
                                getattr(config, "SKILL_HEAL_ONE", None)):
                    if not _heal_decide(key, stat.sp):
                        continue
                elif _cat(skill_id) == 6:
                    if not _sprestore_decide(key + ":spr", stat.sp):
                        continue
            b1, b2 = _ally_target(state, target_key, unit, at)
            return Decision(unit, at, b2, skill_id, b=b1)
        if not _can_attack_new_enemy_gen(state, unit, atype=atype):
            return None
        pos = _enemy_target_pos(state, offered, target_key)
        if pos is None:
            return None
        return _attack(unit, at, pos, skill_id, fb, offered)
    return None



def _combat_attack(state, unit, skills, stat, options, spam_attr, fire_min):
    """Quyet dinh TAN CONG (sau khi da loai heal) - DUNG CHUNG char + pet. 3 che do:
      BOSS  (boss_mode, dungeon): nuke = pick_boss_skill (don dap>don>skill dau), target it mau nhat.
      QUEST (quest_mode, start >6 quai):
            > 6 quai con  -> all-target (neu co) -> ko thi combo AoE -> danh thuong
            <=6 quai con  -> nhu boss + target IT MAU NHAT
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
    if _is_mineral_battle(state):
        return Decision(unit, at, at, config.SKILL_FLEE,
                        b=(3 if unit == config.UNIT_CHAR else 2))

    def low_or_train():
        p = _lowest_hp_enemy(state, offered)
        return p if p is not None else _train_target(es, offered)

    # 1) BOSS mode
    if getattr(state, "boss_mode", False) and es:
        boss = pick_boss_skill(skills)
        pos = low_or_train()
        sk = boss if (boss and sp >= cost(boss)) else config.SKILL_NORMAL
        return _attack(unit, at, pos, sk, fb, offered)

    # 2) QUEST mode (start >6 quai)
    if getattr(state, "quest_mode", False) and es:
        # Unit CO skill hoi (hoi sinh/11010/11009) -> DE DANH SP: SP <= reserve thi danh thuong,
        # giu SP phong turn sau can hoi sinh/hoi mau/hoi SP. Chi SP > reserve moi xai skill atk.
        if _has_support_skill(skills) and sp <= getattr(config, "SUPPORT_RESERVE_SP", 100):
            return _attack(unit, at, low_or_train(), config.SKILL_NORMAL, fb, offered)
        if len(es) > 6:
            allt = pick_alltarget_skill(skills)
            if allt and sp >= cost(allt):
                return _attack(unit, at, _train_target(es, offered), allt, fb, offered)
            combo = pick_combo_skill(skills)   # ko co all-target -> combo AoE thuong
            if combo and sp >= max(fire_min, cost(combo)) and _combo_block_ok(combo, es):
                return _attack(unit, at, _train_target(es, offered), combo, fb, offered)
            return _attack(unit, at, _train_target(es, offered), config.SKILL_NORMAL, fb, offered)
        # <=6 quai -> nhu boss + target it mau nhat
        boss = pick_boss_skill(skills)
        pos = low_or_train()
        sk = boss if (boss and sp >= cost(boss)) else config.SKILL_NORMAL
        return _attack(unit, at, pos, sk, fb, offered)

    # 3) TRAIN mode (combo)
    if stat.sp_max > 0 and sp >= stat.sp_max:
        setattr(state, spam_attr, True)
    combo = pick_combo_skill(skills)
    if (combo and sp >= max(fire_min, cost(combo))
            and (getattr(state, spam_attr) or _combo_block_ok(combo, es))):
        return _attack(unit, at, _train_target(es, offered), combo, fb, offered)
    return _attack(unit, at, _train_target(es, offered), config.SKILL_NORMAL, fb, offered)


def decide_multipet(state, atype, skills, stat, options):
    """DI GIOI SOLO: quyet dinh cho 1 PET RIENG trong so toi da 4 con cung tran (moi con 1 atype
    RIENG: 0,1,3,4 - atype 2 la CHAR). Logic dung GIONG TRAIN mode don gian (combo Hoa Tien/Nem
    Da/Loan Kich neu co du SP+block, khong thi danh thuong) - KHONG lam BOSS/QUEST rieng cho
    truong hop nay (theo yeu cau: "train mode thoi, khong co combo thi danh thuong").
    skills/stat = skill list + Unit (HP/SP) CUA RIENG con pet nay (tu state.multi_pet_skills /
    state.multi_pet[atype]), KHAC voi decide_pet (dung state.skills_pet/state.pet chung 1 con)."""
    offered = _offered_targets(options, atype)
    if not offered:
        return None
    fb = offered[0]
    sp = stat.sp
    es = state.enemy_slots
    if not es:
        return None
    custom = _custom_decision(state, config.UNIT_PET, "pet", skills, stat, options, atype=atype)
    if custom is _CUSTOM_AUTO:
        pass
    elif custom is not None:
        return custom
    if _is_mineral_battle(state):
        return Decision(config.UNIT_PET, atype, atype, config.SKILL_FLEE, b=2)
    # CHI danh khi CO du lieu quai MOI rieng cho ATYPE nay (tranh danh lap tren 0x33 cu - xem
    # _combat_attack ban goc; o day dung dict rieng theo atype vi 4 pet KHONG the dung chung 1
    # bien gen (se dam vao nhau, chi 1 con "thay" du lieu moi moi luot)).
    gen_map = state.last_atk_gen_multipet
    if gen_map.get(atype, -1) == state.enemy_gen:
        return None
    gen_map[atype] = state.enemy_gen
    combo = pick_combo_skill(skills)
    fire_min = getattr(config, "PET_FIRE_MIN_SP", 0)
    if combo and sp >= max(fire_min, _skill_cost(combo)) and _combo_block_ok(combo, es):
        sk = combo
    else:
        sk = config.SKILL_NORMAL
    pos = _train_target(es, offered)
    if pos is None:
        return None
    return _attack(config.UNIT_PET, atype, pos, sk, fb, offered)


def decide_char(state, options, first_turn=False):
    at = state.my_atype
    custom = _custom_decision(state, config.UNIT_CHAR, "char", state.skills_char, state.char, options)
    if custom is _CUSTOM_AUTO:
        pass
    elif custom is not None:
        return custom
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
    if _is_mineral_battle(state):
        return Decision(config.UNIT_CHAR, at, at, config.SKILL_FLEE, b=3)
    return _combat_attack(state, config.UNIT_CHAR, state.skills_char, state.char, options,
                          "char_spam", config.CHAR_FIRE_MIN_SP)


def decide_pet(state, options, first_turn=False):
    at = state.my_atype
    custom = _custom_decision(state, config.UNIT_PET, "pet", state.pet_skills, state.pet, options)
    if custom is _CUSTOM_AUTO:
        pass
    elif custom is not None:
        return custom
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
    if _is_mineral_battle(state):
        return Decision(config.UNIT_PET, at, at, config.SKILL_FLEE, b=2)
    return _combat_attack(state, config.UNIT_PET, state.pet_skills, state.pet, options,
                          "pet_spam", config.PET_FIRE_MIN_SP)
