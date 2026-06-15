# Map Pathfinding (auto đi tới bãi quái) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho bot tự tìm đường liên map (qua cổng dịch chuyển) từ map hiện tại tới train map rồi ra bãi quái, thay vì bắt nhân vật park sẵn trên train map.

**Architecture:** Đồ thị cổng để file riêng `map_gates.json` (`map_id → [{x,y,to}]`), seed từ `Warp_C.dat` đã decode. BFS (`bot/pathfind.py`) ra chuỗi cổng; `client.walk_through_gate` đi tới từng cổng + chờ đổi map; `client.go_to_map` ghép các chặng; tích hợp vào train mode (login sai map → tự đi tới). `train_maps.json` giữ nguyên (chỉ safe+mobs) để không loạn list.

**Tech Stack:** Python 3, unittest (built-in, không cần cài), struct (parse binary), JSON data files.

**Spec:** `docs/superpowers/specs/2026-06-15-map-pathfinding-design.md`

---

## File Structure
- Create `tools/decode_warp.py` — đọc `gamedata/Warp_C.dat` → sinh `map_gates.json`.
- Create `map_gates.json` — đồ thị cổng (sinh ra + bổ sung capture).
- Create `bot/pathfind.py` — BFS `find_path`.
- Create `tests/test_pathfind.py` — unittest cho BFS.
- Modify `bot/config.py` + `bot/config.example.py` — thêm `_load_map_gates()` → `MAP_GATES`.
- Modify `bot/client.py` — thêm `walk_through_gate()`, `go_to_map()`.
- Modify `run_party_digioi.py` — train mode sai map → `go_to_map()`.
- Sync tất cả sang `release/`.

---

## Task 0: Capture cơ chế đi qua cổng (PREREQUISITE — không TDD)

**Mục đích:** Xác nhận đi qua cổng map THƯỜNG hoạt động thế nào (tự đổi map khi giẫm cổng, hay cần gói trigger như Dị Giới `0x14 04000100/08000100`). Đây là rủi ro #1.

- [ ] **Step 1: Bật tcpdump trên emulator game**

Run:
```bash
dev=emulator-5578   # hoặc device đang chạy game (adb devices; tìm com.vtcmobile.gz06)
adb -s $dev root
adb -s $dev shell "rm -f /sdcard/gate.pcap; nohup tcpdump -i any -U -s 0 net 103.82.28.0/24 and port 6614 -w /sdcard/gate.pcap >/dev/null 2>&1 &"
```

- [ ] **Step 2: Người chơi đi BỘ qua 1 cổng map thường (1 lần), đứng yên trước/sau ~3s**

(Thao tác tay trong game: đi nhân vật tới 1 cổng dịch chuyển trên 1 map thường → sang map khác.)

- [ ] **Step 3: Pull + phân tích**

Run:
```bash
adb -s $dev shell "pkill -INT tcpdump"; sleep 1
MSYS_NO_PATHCONV=1 adb -s $dev pull //sdcard/gate.pcap E:/Claude/ATS/gate.pcap
```
Dùng parser pcap có sẵn (xem các script phân tích trong lịch sử: XOR 0xAD, frame `c0 91 [len] 00 00 [op] [payload]`) để xem chuỗi C2S quanh lúc đổi map: có chỉ gói `0x06` (di chuyển) rồi map tự đổi, hay có gói trigger (vd `0x14 ...`).

- [ ] **Step 4: Ghi kết luận vào spec**

Cập nhật mục "Rủi ro #1" trong spec: cơ chế đúng là gì. Kết quả này quyết định nội dung `walk_through_gate` ở Task 5 (nếu cần trigger packet thì thêm; nếu tự đổi thì chỉ move + chờ).

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-06-15-map-pathfinding-design.md
git commit -m "docs: ket luan co che di qua cong (tu capture gate.pcap)"
```

---

## Task 1: Decoder Warp_C.dat → sinh map_gates.json

**Files:**
- Create: `tools/decode_warp.py`
- Create: `map_gates.json` (output)
- Test: `tests/test_decode_warp.py`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_decode_warp.py
import unittest, struct, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.decode_warp import parse_warp

class TestDecodeWarp(unittest.TestCase):
    def test_parse_two_records(self):
        # header=2, roi 2 record 16B: [id u32][src u16][dst u16][x u32][y u32]
        blob = struct.pack("<I", 2)
        blob += struct.pack("<IHHII", 21699, 12001, 11804, 310, 1530)
        blob += struct.pack("<IHHII", 21701, 12061, 11806, 160, 900)
        rows = parse_warp(blob)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {"id": 21699, "src": 12001, "dst": 11804, "x": 310, "y": 1530})
        self.assertEqual(rows[1]["src"], 12061)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test cho FAIL**

Run: `python -m unittest tests.test_decode_warp -v`
Expected: FAIL — `ModuleNotFoundError: tools.decode_warp` (chưa tạo).

- [ ] **Step 3: Viết `tools/decode_warp.py`**

```python
"""Decode Warp_C.dat (game VTC) -> map_gates.json.
Record 16B: [warp_id u32][srcMap u16][dstMap u16][x u32][y u32], header u32 = so record."""
import struct, json, os, sys

def parse_warp(blob: bytes):
    cnt = struct.unpack_from("<I", blob, 0)[0]
    rows = []
    off = 4
    for _ in range(cnt):
        if off + 16 > len(blob):
            break
        wid, src, dst, x, y = struct.unpack_from("<IHHII", blob, off)
        rows.append({"id": wid, "src": src, "dst": dst, "x": x, "y": y})
        off += 16
    return rows

def build_gates(rows):
    """rows -> {maps: {src_map: {gates:[{x,y,to}]}}}. Gom theo srcMap."""
    maps = {}
    for r in rows:
        m = maps.setdefault(str(r["src"]), {"gates": []})
        m["gates"].append({"x": r["x"], "y": r["y"], "to": r["dst"]})
    return {"_note": "Do thi cong di chuyen. map_id -> gates[{x,y,to}]. Seed tu Warp_C.dat + capture.",
            "maps": maps}

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "gamedata/Warp_C.dat"
    out = sys.argv[2] if len(sys.argv) > 2 else "map_gates.json"
    rows = parse_warp(open(src, "rb").read())
    data = build_gates(rows)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Decoded {len(rows)} warps -> {len(data['maps'])} maps -> {out}")
```

- [ ] **Step 4: Chạy test cho PASS**

Run: `python -m unittest tests.test_decode_warp -v`
Expected: PASS.

- [ ] **Step 5: Sinh map_gates.json thật**

Run: `python tools/decode_warp.py gamedata/Warp_C.dat map_gates.json`
Expected: in `Decoded 41 warps -> N maps -> map_gates.json`. Mở file kiểm tra map 12001/12061 có gate.

- [ ] **Step 6: Commit**

```bash
git add tools/decode_warp.py tests/test_decode_warp.py map_gates.json
git commit -m "feat: decode Warp_C.dat -> map_gates.json (seed do thi cong)"
```

---

## Task 2: Loader `_load_map_gates()` trong config

**Files:**
- Modify: `bot/config.py` (thêm sau `TRAIN_MAPS = _load_train_maps()`)
- Modify: `bot/config.example.py` (giống hệt)
- Test: `tests/test_load_gates.py`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_load_gates.py
import unittest, json, os, tempfile, importlib, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestLoadGates(unittest.TestCase):
    def test_load(self):
        from bot.config import _load_map_gates  # ham moi
        d = {"maps": {"12831": {"gates": [{"x": 310, "y": 1530, "to": 11804}]}}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(d, f); path = f.name
        g = _load_map_gates(path)
        self.assertEqual(g[12831], [(310, 1530, 11804)])
        os.unlink(path)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test cho FAIL**

Run: `python -m unittest tests.test_load_gates -v`
Expected: FAIL — `ImportError: cannot import name '_load_map_gates'`.

- [ ] **Step 3: Thêm loader vào `bot/config.py`** (ngay sau dòng `TRAIN_MAPS = _load_train_maps()`)

```python
def _load_map_gates(path=None):
    """Doc map_gates.json -> {map_id:int -> [(x,y,to), ...]}. Khong co file -> {}."""
    import json, os
    f = path or os.path.join(os.path.dirname(__file__), os.pardir, "map_gates.json")
    out = {}
    try:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        for k, v in d.get("maps", {}).items():
            out[int(k)] = [(int(g["x"]), int(g["y"]), int(g["to"])) for g in v.get("gates", [])]
    except Exception:
        pass
    return out
MAP_GATES = _load_map_gates()
```

- [ ] **Step 4: Copy y hệt vào `bot/config.example.py`** (cùng vị trí, cùng code).

- [ ] **Step 5: Chạy test cho PASS**

Run: `python -m unittest tests.test_load_gates -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add bot/config.py bot/config.example.py tests/test_load_gates.py
git commit -m "feat: config _load_map_gates -> MAP_GATES"
```

---

## Task 3: BFS `find_path` trong `bot/pathfind.py`

**Files:**
- Create: `bot/pathfind.py`
- Test: `tests/test_pathfind.py`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_pathfind.py
import unittest, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot.pathfind import find_path

# graph: map_id -> [(x,y,to)]
G = {
    12001: [(310, 1530, 11804)],
    11804: [(50, 60, 12831), (70, 80, 11805)],
    12831: [],
}

class TestFindPath(unittest.TestCase):
    def test_same_map_empty(self):
        self.assertEqual(find_path(G, 12831, 12831), [])
    def test_two_hops(self):
        self.assertEqual(find_path(G, 12001, 12831),
                         [(310, 1530, 11804), (50, 60, 12831)])
    def test_no_path(self):
        self.assertIsNone(find_path(G, 12831, 12001))
    def test_unknown_src(self):
        self.assertIsNone(find_path(G, 99999, 12831))

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test cho FAIL**

Run: `python -m unittest tests.test_pathfind -v`
Expected: FAIL — `ModuleNotFoundError: bot.pathfind`.

- [ ] **Step 3: Viết `bot/pathfind.py`**

```python
"""Tim duong lien map qua cong dich chuyen (BFS tren do thi co huong MAP_GATES)."""
from collections import deque

def find_path(graph, src_map, dst_map):
    """graph: {map_id -> [(x,y,to), ...]}. Tra:
      []   neu da o dst (src==dst)
      list [(gate_x, gate_y, next_map), ...] = chuoi cong NGAN nhat
      None neu khong co duong (hoac src khong co trong graph)."""
    if src_map == dst_map:
        return []
    if src_map not in graph:
        return None
    visited = {src_map}
    # queue chua (map_hien_tai, duong_di_toi_no)
    q = deque([(src_map, [])])
    while q:
        cur, path = q.popleft()
        for (x, y, to) in graph.get(cur, []):
            if to in visited:
                continue
            np = path + [(x, y, to)]
            if to == dst_map:
                return np
            visited.add(to)
            q.append((to, np))
    return None
```

- [ ] **Step 4: Chạy test cho PASS**

Run: `python -m unittest tests.test_pathfind -v`
Expected: PASS (4 test).

- [ ] **Step 5: Commit**

```bash
git add bot/pathfind.py tests/test_pathfind.py
git commit -m "feat: pathfind.find_path (BFS do thi cong)"
```

---

## Task 4: `walk_through_gate()` trong client (LIVE — test tay)

**Files:**
- Modify: `bot/client.py` (thêm method, cạnh `navigate_to`/`go_to_town`)

> Nội dung phụ thuộc Task 0. Mặc định dưới đây = đi tới cổng + chờ map đổi (giống thoát Dị Giới nhưng KHÔNG gói trigger). **Nếu Task 0 cho thấy cần gói trigger, thêm vào chỗ đánh dấu.**

- [ ] **Step 1: Thêm method vào `bot/client.py`**

```python
    def walk_through_gate(self, x: int, y: int, expected_map: int,
                          step_wait: float = 1.5, timeout: float = 40.0) -> bool:
        """Di toi cong (x,y) roi cho current_map doi sang expected_map.
        Bat flee_mode ne quai doc duong (giong navigate_to). Tra True neu da sang dung map."""
        log.info("[%s] -> cong (%d,%d) sang map %s", self._label, x, y, expected_map)
        self.flee_mode = True
        t0 = time.time()
        while time.time() - t0 < timeout:
            if not self.running:
                return False
            if self.current_map == expected_map:
                log.info("[%s] da qua cong -> map %s", self._label, expected_map)
                return True
            if self.in_combat(idle_secs=1.5):
                time.sleep(0.5); continue
            self.move_to(x, y)
            # >>> NEU Task 0 cho thay can goi TRIGGER khi toi cong, gui o day <<<
            #     (vd: self.send(0x14, bytes.fromhex("...")))
            time.sleep(step_wait)
        log.warning("[%s] KET o cong (%d,%d): map van la %s (can map %s)",
                    self._label, x, y, self.current_map, expected_map)
        return False
```

- [ ] **Step 2: Kiểm tra import (chạy thử)**

Run: `python -c "import bot.client; print('ok')"`
Expected: in `ok` (không lỗi cú pháp).

- [ ] **Step 3: Test tay (1 acc)** — sau khi có ít nhất 1 cổng thật trong `map_gates.json`:
  - Cho 1 acc đứng ở map nguồn, gọi `walk_through_gate(x, y, to)` (qua REPL/đoạn test) → quan sát log đổi map.
  - Xác nhận bật flee không bị kẹt battle, tới cổng thì map đổi.

- [ ] **Step 4: Commit**

```bash
git add bot/client.py
git commit -m "feat: client.walk_through_gate (di qua cong + cho doi map)"
```

---

## Task 5: `go_to_map()` trong client (LIVE — test tay)

**Files:**
- Modify: `bot/client.py` (thêm sau `walk_through_gate`)

- [ ] **Step 1: Thêm method**

```python
    def go_to_map(self, target_map: int, max_sec: float = 180.0) -> bool:
        """Tu di tu map hien tai toi target_map qua cac cong (BFS MAP_GATES).
        Tra True neu toi noi (current_map == target_map)."""
        from bot import pathfind
        cur = self.current_map
        if cur == target_map:
            return True
        if cur is None:
            log.warning("[%s] go_to_map: chua biet map hien tai", self._label); return False
        path = pathfind.find_path(config.MAP_GATES, cur, target_map)
        if path is None:
            log.warning("[%s] go_to_map: KHONG co duong %s -> %s (thieu cong trong map_gates.json)",
                        self._label, cur, target_map)
            return False
        log.info("[%s] go_to_map %s -> %s qua %d cong", self._label, cur, target_map, len(path))
        t0 = time.time()
        for (x, y, nxt) in path:
            if not self.running or time.time() - t0 > max_sec:
                return False
            if not self.walk_through_gate(x, y, nxt):
                return False   # ket 1 chang -> dung (da log trong walk_through_gate)
        ok = self.current_map == target_map
        log.info("[%s] go_to_map xong: map=%s (dich %s) -> %s",
                 self._label, self.current_map, target_map, "OK" if ok else "CHUA TOI")
        return ok
```

- [ ] **Step 2: Kiểm tra import**

Run: `python -c "import bot.client; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Test tay** — 1 acc ở map có đường tới train map (đủ cổng trong `map_gates.json`): gọi `go_to_map(train_map_id)` → log đi từng cổng → tới nơi.

- [ ] **Step 4: Commit**

```bash
git add bot/client.py
git commit -m "feat: client.go_to_map (BFS + di tung cong toi train map)"
```

---

## Task 6: Tích hợp vào train mode (login sai map → tự đi tới)

**Files:**
- Modify: `run_party_digioi.py` — nhánh leader `if not self_map_ok:` (hiện log "HUY CA PARTY")

- [ ] **Step 1: Sửa nhánh leader sai map**

Tìm trong `run_party_digioi.py` (mục `if is_leader:` → `if not self_map_ok:`). THAY khối hiện tại bằng: thử `go_to_map(sc)` trước; thành công → coi như đúng map (tiếp tục train); thất bại → giữ hành vi cũ (HUY CA PARTY).

```python
                if not self_map_ok:
                    # Thu TU DI toi train map qua cong (pathfinding). Toi noi -> train binh thuong.
                    log.info("[%s] (LEADER) login map %s != train map %s -> thu tu di toi...",
                             label, c.current_map, sc)
                    if c.go_to_map(sc):
                        login_map = c.current_map      # da toi train map
                        self_map_ok = True
                    if not self_map_ok:
                        _reason("leader sai map + khong tu di toi duoc (thieu cong/map_gates) "
                                "-> can park nhan vat tay")
                        log.warning("[%s] (LEADER) KHONG tu toi train map %s duoc -> HUY CA PARTY. "
                                    "CACH SUA: dua nhan vat ve map %s roi thoat game tai do, "
                                    "HOAC bo sung cong vao map_gates.json.", label, sc, sc)
                        st["leader_bad"].set()
                        _daily_then_quit(); return
                st["leader_ok"].set()
```

- [ ] **Step 2: Sửa nhánh MEMBER sai map tương tự** (mục `else:` → `if not self_map_ok:` của member)

```python
                if not self_map_ok:
                    log.info("[%s] (member) login map %s != train map %s -> thu tu di toi...",
                             label, c.current_map, sc)
                    if c.go_to_map(sc):
                        login_map = c.current_map; self_map_ok = True
                    if not self_map_ok:
                        _reason("member sai map + khong tu di toi duoc (thieu cong)")
                        log.warning("[%s] (member) KHONG tu toi train map %s -> THOAT. "
                                    "CACH SUA: dua nhan vat ve map %s roi thoat game, HOAC "
                                    "bo sung cong vao map_gates.json.", label, sc, sc)
                        _daily_then_quit(); return
```

- [ ] **Step 3: Kiểm tra cú pháp**

Run: `python -c "import ast; ast.parse(open('run_party_digioi.py',encoding='utf-8').read()); print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Test tay** — 1 party có train map + đủ cổng: cho leader login ở map khác → bot tự đi tới train map → lập party → train. Xem log `go_to_map ... OK`.

- [ ] **Step 5: Commit**

```bash
git add run_party_digioi.py
git commit -m "feat: train mode sai map -> tu di toi train map (pathfinding) thay vi huy party"
```

---

## Task 7: Sync release/ + đóng gói

**Files:**
- Copy sang `release/`: `bot/client.py`, `bot/config.py`, `bot/config.example.py`, `run_party_digioi.py`, `map_gates.json`, `bot/pathfind.py`

- [ ] **Step 1: Sync**

```bash
cp bot/client.py bot/config.py bot/config.example.py bot/pathfind.py release/bot/
cp run_party_digioi.py map_gates.json release/
```

- [ ] **Step 2: Commit + push**

```bash
git add release/
git commit -m "chore: sync release (map pathfinding)"
git push
```

---

## Self-Review (đã làm khi viết)
- Spec coverage: data 2 file (Task 1,2) · BFS (Task 3) · walk_through_gate (Task 4) · go_to_map (Task 5) · tích hợp train mode (Task 6) · capture cơ chế (Task 0) · sync release (Task 7). Edit Map giữ nguyên (không có task — đúng spec).
- Type nhất quán: `MAP_GATES`/graph = `{map_id:int -> [(x,y,to)]}` xuyên suốt; `find_path` trả `[]/list/None` đồng nhất Task 3↔5.
- Không placeholder code (trừ chỗ trigger ở Task 4 — phụ thuộc Task 0, đã đánh dấu rõ).
