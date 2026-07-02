# Android Foreground Service Foundation (đa tài khoản, mode Train) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho app Android chạy nhiều tài khoản song song ở mode Train (đòn thường/combo, không boss/quest/party/Dị Giới), điều khiển qua Compose UI đơn giản (danh sách account, start/stop, trạng thái) — chưa có bubble nổi (sub-project sau).

**Architecture:** 1 `BotForegroundService` (Kotlin) khởi động Chaquopy Python 1 lần; mỗi account chạy 1 Kotlin thread gọi vào 1 hàm Python `run_train(username, password, server_key, on_status)` port gần như nguyên vẹn từ `bot/client.py::GameClient` + `bot/combat.py` + `bot/state.py` (đã xác nhận qua đọc code: các file này KHÔNG phụ thuộc party/leader — phần "solo train" gần giống hệt `run_grind.py` ở PC, chỉ khác input credentials tới từ UI thay vì `config.py`). Lớp `bot/protocol.py` (XOR thuần Python) được thay bằng bản delegate sang `bot_native_bridge`/`ProtocolBridge` (đã có từ Phase 1) để giữ đúng yêu cầu bảo vệ giao thức bằng native code — đây là lý do DUY NHẤT cần sửa `protocol.py`, các file `client.py`/`combat.py`/`state.py`/`auth.py`/`login.py` được copy gần như nguyên vẹn.

**Tech Stack:** Chaquopy (Python trong Android), Kotlin coroutine/thread, Jetpack Compose, JSON (`org.json`) cho lưu trữ local, JNI protocol-native đã có từ Phase 1.

---

## Bối cảnh đã xác nhận (đọc trực tiếp code, không đoán)

- `bot/protocol.py` hiện có `xor(data)`, `build_packet(opcode, payload)`, `encode(opcode, payload)` (= `xor(build_packet(...))`), `parse_stream(decoded: bytes) -> (list[(opcode, full_packet_bytes)], consumed_bytes)`. `parse_stream` nhận buffer **ĐÃ xor xong** (`decoded`), KHÔNG tự xor.
- `bot/client.py::GameClient` (L459 trở đi) dùng `protocol.xor`/`protocol.encode`/`protocol.parse_stream` trong vòng lặp nhận (buffer tích luỹ qua nhiều lần `sock.recv()`, dùng `consumed_bytes` để cắt phần đã xử lý khỏi buffer — đây là lý do bản native hiện tại (`bot_native_bridge.decode_stream`, trả `List<bytes>` KHÔNG có consumed-count) chưa đủ để thay thế `parse_stream` 1-1; cần bổ sung.
- `bot/combat.py::decide_char`/`decide_pet`/`_combat_attack` (nhánh TRAIN, dòng 504-511) KHÔNG có nhánh boss/quest/party — dùng trực tiếp được, không cần sửa.
- `bot/state.py::BattleState` tự chứa, không phụ thuộc client/party.
- `bot/config.py` nạp nhiều file JSON tham chiếu (`pets.json`, `skills_data.json`, `servers.json`, `train_maps.json`...) bằng `os.path.join(_base_dir(), "...")` VÀ tự nạp `ACCOUNTS`/`PARTY_CONFIG` từ file cấu hình riêng của PC (không dùng trên Android — Android có accounts.json riêng do Kotlin quản lý).
- `run_grind.py` (PC, 61 dòng) là mẫu tham khảo tốt nhất cho vòng lặp solo-train: `login()` → `GameClient(user_id, token)` → `c.connect()` → thread `wander()` gọi `c.send(0x06, ...)` khi `not c.in_combat()` → vòng lặp chính chỉ log trạng thái mỗi 30s.

## File Structure

```
android/app/src/main/python/
  train_bot/
    __init__.py
    protocol.py        # THAY THE: delegate sang bot_native_bridge (KHONG xor thuan Python nua)
    config.py           # RUT GON tu bot/config.py: chi hang so + PET_SKILLS/SKILL_INFO, BO ACCOUNTS/PARTY_CONFIG
    auth.py              # COPY nguyen ven tu bot/auth.py
    login.py             # COPY tu bot/login.py (co the xoa doan doc config.USERNAME/PASSWORD mac dinh)
    state.py             # COPY nguyen ven tu bot/state.py
    combat.py            # COPY nguyen ven tu bot/combat.py
    client.py            # COPY tu bot/client.py, GIU NGUYEN class GameClient (khong xoa code party -
                          # don gian hon la khong goi toi, tranh sua nham logic dang hoat dong tren PC)
    train_runner.py      # MOI: ham run_train(...) - phong theo run_grind.py, dung threading + callback status
android/app/src/main/assets/train_bot_data/
    pets.json, skills_data.json, servers.json, train_maps.json   # copy tu goc repo (chi doc, khong sua)
android/app/src/main/cpp/protocol.cpp / protocol.h   # SUA: decodeStream tra them so byte da tieu thu
android/app/src/main/cpp/protocol_jni.cpp             # SUA: JNI signature moi
android/app/src/main/java/com/tsbot/android/
    ProtocolBridge.kt                # SUA: decodeStream tra Pair(frames, consumedBytes)
    AccountStore.kt                  # MOI: doc/ghi accounts.json bang org.json
    AccountStatus.kt                 # MOI: data class trang thai 1 account
    BotForegroundService.kt          # MOI: Service quan ly nhieu thread Python
    MainActivity.kt                  # SUA: form quan ly account list + start/stop (thay smoke-test cu)
android/app/src/main/python/bot_native_bridge.py   # SUA: decode_stream tra (frames, consumed)
```

---

### Task 1: Mở rộng `protocol-native` để trả về số byte đã tiêu thụ

**Files:**
- Modify: `android/app/src/main/cpp/protocol.h`
- Modify: `android/app/src/main/cpp/protocol.cpp`
- Modify: `android/app/src/main/cpp/protocol_jni.cpp`
- Modify: `android/app/src/main/java/com/tsbot/android/ProtocolBridge.kt`
- Modify: `android/app/src/main/cpp/test/protocol_test.cpp`
- Test: instrumented `android/app/src/androidTest/java/com/tsbot/android/ProtocolBridgeTest.kt`

Bản hiện tại của `decodeStream` (từ Phase 1) chỉ trả về danh sách frame hoàn chỉnh, không cho biết đã "ăn" bao nhiêu byte từ buffer đầu vào — client.py gốc cần con số này để cắt phần đã xử lý khỏi buffer tích luỹ (`bot/protocol.py::parse_stream` trả `(frames, consumed)`).

- [ ] **Step 1: Đổi chữ ký C++ `decodeStream` để trả cả consumed-length**

Trong `android/app/src/main/cpp/protocol.h`, đổi:
```cpp
std::vector<std::vector<uint8_t>> decodeStream(const std::vector<uint8_t>& wireBuf);
```
thành:
```cpp
struct DecodeResult {
    std::vector<std::vector<uint8_t>> frames;
    size_t consumed;   // so byte cua wireBuf da duoc xu ly (frame hoan chinh); phan con lai la du lieu chua du
};
DecodeResult decodeStream(const std::vector<uint8_t>& wireBuf);
```

- [ ] **Step 2: Cập nhật `protocol.cpp`**

Trong `decodeStream`, sau khi XOR toàn bộ `wireBuf` thành `plain`, khi vòng quét không tìm thêm frame hoàn chỉnh nào nữa (magic không khớp hoặc `plen` vượt quá phần còn lại), gán `result.consumed = i` (vị trí con trỏ quét hiện tại, TRƯỚC byte chưa xử lý được) thay vì bỏ qua như bản cũ. Ví dụ khung xử lý:
```cpp
DecodeResult decodeStream(const std::vector<uint8_t>& wireBuf) {
    DecodeResult result;
    std::vector<uint8_t> plain = xorBuf(wireBuf);
    size_t i = 0;
    size_t n = plain.size();
    while (i + 7 <= n) {
        if (!(plain[i] == 0xc0 && plain[i+1] == 0x91)) { i++; continue; }
        uint16_t plen = plain[i+2] | (plain[i+3] << 8);
        if (plen < 7 || i + plen > n) break;   // frame chua du, dung lai
        result.frames.emplace_back(plain.begin() + i, plain.begin() + i + plen);
        i += plen;
    }
    result.consumed = i;
    return result;
}
```

- [ ] **Step 3: Cập nhật `protocol_jni.cpp`**

`Java_com_tsbot_android_ProtocolBridge_nativeDecodeStream` hiện trả `Array<ByteArray>` — đổi để trả về 1 mảng gồm `N+1` phần tử: `N` frame đầu, phần tử CUỐI là mảng 1 phần tử `int` (hoặc dùng `IntArray` riêng) chứa `consumed`. Cách đơn giản nhất tránh đổi kiểu trả về JNI phức tạp: trả về `ByteArray` đầu tiên LÀ 4-byte little-endian của `consumed`, các phần tử tiếp theo là các frame. Đặt tên hàm `nativeDecodeStream` giữ nguyên, chỉ đổi format phần tử đầu:

```cpp
JNIEXPORT jobjectArray JNICALL
Java_com_tsbot_android_ProtocolBridge_nativeDecodeStream(JNIEnv* env, jobject, jbyteArray wire) {
    jsize len = env->GetArrayLength(wire);
    std::vector<uint8_t> buf(len);
    env->GetByteArrayRegion(wire, 0, len, reinterpret_cast<jbyte*>(buf.data()));
    tsbot::DecodeResult r = tsbot::decodeStream(buf);

    jclass byteArrayClass = env->FindClass("[B");
    jobjectArray out = env->NewObjectArray(r.frames.size() + 1, byteArrayClass, nullptr);

    jbyteArray consumedArr = env->NewByteArray(4);
    jbyte consumedBytes[4] = {
        (jbyte)(r.consumed & 0xFF), (jbyte)((r.consumed >> 8) & 0xFF),
        (jbyte)((r.consumed >> 16) & 0xFF), (jbyte)((r.consumed >> 24) & 0xFF)
    };
    env->SetByteArrayRegion(consumedArr, 0, 4, consumedBytes);
    env->SetObjectArrayElement(out, 0, consumedArr);

    for (size_t k = 0; k < r.frames.size(); k++) {
        jbyteArray f = env->NewByteArray(r.frames[k].size());
        env->SetByteArrayRegion(f, 0, r.frames[k].size(),
                                 reinterpret_cast<const jbyte*>(r.frames[k].data()));
        env->SetObjectArrayElement(out, k + 1, f);
    }
    return out;
}
```

- [ ] **Step 4: Cập nhật `ProtocolBridge.kt`**

```kotlin
object ProtocolBridge {
    init { System.loadLibrary("tsbot_protocol") }
    private external fun nativeEncodeFrame(opcode: Int, payload: ByteArray): ByteArray
    private external fun nativeDecodeStream(wire: ByteArray): Array<ByteArray>

    fun encodeFrame(opcode: Int, payload: ByteArray): ByteArray = nativeEncodeFrame(opcode, payload)

    /** Tra ve Pair(danh sach frame hoan chinh, so byte da tieu thu tu dau wire). */
    fun decodeStream(wire: ByteArray): Pair<List<ByteArray>, Int> {
        val raw = nativeDecodeStream(wire)
        val consumedBytes = raw[0]
        val consumed = (consumedBytes[0].toInt() and 0xFF) or
            ((consumedBytes[1].toInt() and 0xFF) shl 8) or
            ((consumedBytes[2].toInt() and 0xFF) shl 16) or
            ((consumedBytes[3].toInt() and 0xFF) shl 24)
        val frames = raw.drop(1)
        return Pair(frames, consumed)
    }
}
```

- [ ] **Step 5: Cập nhật test C++ host (`protocol_test.cpp`)**

Thêm 1 assertion mới vào `test_decode_partial_stream_waits_for_more_bytes` xác nhận `result.consumed` bằng đúng độ dài phần đã xử lý (dùng lại wire vector test đã có, cắt bớt 3 byte cuối để mô phỏng frame chưa đủ — xác nhận `consumed` = 0 khi frame đầu tiên chưa đủ dữ liệu, và bằng độ dài đầy đủ khi có đủ). Build lại bằng cùng cách Task 2 (Phase 1) đã làm: cross-compile bằng NDK clang++ target `aarch64-linux-android24`, push qua `adb`, chạy trên thiết bị (dùng `-static-libstdc++`, KHÔNG static link toàn bộ — đã gặp lỗi "TLS segment underaligned" trên Bionic ARM64 nếu làm vậy).

Run:
```bash
"C:\Android\ndk\26.3.11579264\toolchains\llvm\prebuilt\windows-x86_64\bin\clang++.exe" \
  --target=aarch64-linux-android24 -static-libstdc++ -std=c++17 \
  android/app/src/main/cpp/protocol.cpp android/app/src/main/cpp/test/protocol_test.cpp \
  -o /tmp/protocol_test
adb push /tmp/protocol_test /data/local/tmp/protocol_test
adb shell chmod +x /data/local/tmp/protocol_test
adb shell /data/local/tmp/protocol_test
```
Expected: `ALL PASS`.

- [ ] **Step 6: Cập nhật instrumented test `ProtocolBridgeTest.kt`**

Sửa test hiện có (dùng `ProtocolBridge.decodeStream`) để unpack `Pair`, xác nhận `consumed` đúng bằng độ dài wire input khi có đúng 1 frame trọn vẹn. Build + chạy trên thiết bị:
```bash
cd android
export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew connectedDebugAndroidTest
```
Kiểm tra report XML tại `android/app/build/outputs/androidTest-results/connected/**/TEST-*.xml` có `failures="0"` (KHÔNG chỉ tin `BUILD SUCCESSFUL` — bài học từ Phase 1: sourceSet sai chỗ vẫn báo BUILD SUCCESSFUL nhưng 0 test chạy).

- [ ] **Step 7: Commit**

```bash
git add android/app/src/main/cpp/protocol.h android/app/src/main/cpp/protocol.cpp \
        android/app/src/main/cpp/protocol_jni.cpp android/app/src/main/cpp/test/protocol_test.cpp \
        android/app/src/main/java/com/tsbot/android/ProtocolBridge.kt \
        android/app/src/androidTest/java/com/tsbot/android/ProtocolBridgeTest.kt
git commit -m "feat(android): decodeStream tra them so byte da tieu thu, can cho buffer streaming cua client.py goc"
```

---

### Task 2: `bot_native_bridge.py` — cập nhật theo API mới + shim `protocol.py`

**Files:**
- Modify: `android/app/src/main/python/bot_native_bridge.py`
- Create: `android/app/src/main/python/train_bot/__init__.py`
- Create: `android/app/src/main/python/train_bot/protocol.py`
- Test: `android/app/src/androidTest/java/com/tsbot/android/TrainBotProtocolTest.kt`

- [ ] **Step 1: Sửa `bot_native_bridge.decode_stream` để trả `(frames, consumed)`**

```python
def decode_stream(wire_buf: bytes):
    """Tra ve (list[bytes frame hoan chinh], so byte da tieu thu tu dau wire_buf)."""
    result = _bridge().INSTANCE.decodeStream(bytearray(wire_buf))
    pair = result  # Kotlin Pair<List<ByteArray>, Int>
    frames_list = pair.first()
    consumed = pair.second()
    frames = [bytes(frames_list.get(i)) for i in range(frames_list.size())]
    return frames, consumed
```
(Ghi chú cho engineer: xác nhận Chaquopy truy cập `kotlin.Pair` qua `.first()`/`.second()` — nếu Chaquopy không proxy được method Kotlin dạng property, đổi `ProtocolBridge.decodeStream` ở Task 1 sang trả 1 `data class DecodeResult(val frames: List<ByteArray>, val consumed: Int)` với getter Java-style `getFrames()`/`getConsumed()` thay vì `Pair`, dễ tương thích Chaquopy hơn — kiểm tra bằng test thực tế trước khi chốt.)

- [ ] **Step 2: Tạo `train_bot/__init__.py` rỗng** (đánh dấu package).

- [ ] **Step 3: Tạo `train_bot/protocol.py` — shim thay thế `bot/protocol.py`, giữ NGUYÊN chữ ký hàm để `client.py` copy sang không cần sửa**

```python
"""Thay the bot/protocol.py ban goc (XOR thuan Python) - o Android moi XOR/frame
di qua protocol-native (C++/JNI) qua bot_native_bridge, giu dung API cu (encode/
parse_stream/xor) de train_bot/client.py (copy tu bot/client.py) khong can sua gi."""
import bot_native_bridge as _bridge

MAGIC = b"\xc0\x91"

OP_LOGIN = 0x01
OP_HEARTBEAT = 0x0A
OP_FULLSTAT = 0x0B
OP_MOB_INFO = 0x0C
OP_PLAYER_STATE = 0x0D
OP_TELEPORT = 0x44
OP_INVITE = 0x52
OP_COMBAT = 0x32
OP_STAT_UPD = 0x33
OP_BATTLE_START = 0x34
OP_ACTIONS = 0x35
OP_BATTLE_ENTER = 0x41


def encode(opcode: int, payload: bytes) -> bytes:
    return _bridge.encode_frame(opcode, payload)


def xor(data: bytes) -> bytes:
    """KHONG con dung truc tiep trong client.py (parse_stream thay the), giu lai
    chi de tuong thich neu co cho nao goi rieng le - danh dau loi neu that su goi toi."""
    raise NotImplementedError("protocol.xor() da thay bang native decode_stream - kiem tra cho goi ham nay")


def parse_stream(raw_wire_buf: bytes):
    """KHAC bot/protocol.py goc: ham nay nhan RAW WIRE (chua xor) thay vi da-xor,
    vi native decode_stream tu lam xor ben trong. Neu client.py goc truyen 'decoded'
    (da xor roi) vao day, PHAI sua lai diem goi trong client.py de truyen raw wire
    truc tiep - xem Task 3 Step ve _recv_loop."""
    frames, consumed = _bridge.decode_stream(raw_wire_buf)
    return [(f[6], f) for f in frames], consumed
```

- [ ] **Step 4: Viết instrumented test xác nhận round-trip qua shim mới**

`android/app/src/androidTest/java/com/tsbot/android/TrainBotProtocolTest.kt`:
```kotlin
package com.tsbot.android

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.Assert.assertEquals

@RunWith(AndroidJUnit4::class)
class TrainBotProtocolTest {
    @Before
    fun setup() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        if (!Python.isStarted()) Python.start(AndroidPlatform(ctx))
    }

    @Test
    fun encodeDecodeRoundTripThroughShim() {
        val py = Python.getInstance()
        val mod = py.getModule("train_bot.protocol")
        val encoded = mod.callAttr("encode", 0x32, "AB".toByteArray())
        val wire = encoded.toJava(ByteArray::class.java)
        val result = mod.callAttr("parse_stream", wire)
        val list = result.asList()
        val frames = list[0].asList()
        val consumed = list[1].toInt()
        assertEquals(1, frames.size)
        assertEquals(wire.size, consumed)
        val opcode = frames[0].asList()[0].toInt()
        assertEquals(0x32, opcode)
    }
}
```

- [ ] **Step 5: Build + chạy test trên thiết bị**

```bash
cd android
export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew connectedDebugAndroidTest
```
Kiểm tra XML report `TEST-com.tsbot.android.TrainBotProtocolTest.xml` có `failures="0"`. Nếu lỗi do Chaquopy không hiểu `kotlin.Pair`, quay lại Task 1 Step 4 đổi sang `data class DecodeResult`.

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/python/bot_native_bridge.py android/app/src/main/python/train_bot/ \
        android/app/src/androidTest/java/com/tsbot/android/TrainBotProtocolTest.kt
git commit -m "feat(android): shim train_bot/protocol.py thay bot/protocol.py, dung native decode co consumed-count"
```

---

### Task 3: Copy `config.py` (rút gọn), `auth.py`, `login.py`, `state.py`, `combat.py`, `client.py` vào `train_bot/`

**Files:**
- Create: `android/app/src/main/python/train_bot/config.py`
- Create: `android/app/src/main/python/train_bot/auth.py`
- Create: `android/app/src/main/python/train_bot/login.py`
- Create: `android/app/src/main/python/train_bot/state.py`
- Create: `android/app/src/main/python/train_bot/combat.py`
- Create: `android/app/src/main/python/train_bot/client.py`
- Create: `android/app/src/main/assets/train_bot_data/pets.json` (copy từ `E:\Claude\ATS\pets.json`)
- Create: `android/app/src/main/assets/train_bot_data/skills_data.json` (copy từ `E:\Claude\ATS\skills_data.json`)
- Read (không sửa): `E:\Claude\ATS\bot\config.py`, `bot\auth.py`, `bot\login.py`, `bot\state.py`, `bot\combat.py`, `bot\client.py`

Đây là task lớn nhất, cần đọc kỹ file gốc trước khi copy (engineer PHẢI đọc toàn bộ `bot/client.py` — 3462 dòng — vì đang copy gần như nguyên vẹn, không phải viết mới).

- [ ] **Step 1: Tạo `train_bot/config.py` — bản RÚT GỌN của `bot/config.py`**

Copy nguyên các hằng số sau từ `bot/config.py` (không đổi giá trị): `HEAL_HP_THRESHOLD`, `HEAL_SP_COST`, `PET_FIRE_MIN_SP`, `CHAR_FIRE_MIN_SP`, `SKILL_NORMAL`, `SKILL_ROCK`, `SKILL_FIRE`, `SKILL_HEAL_ALL`, `SKILL_HEAL_ONE`, `SKILL_DEFEND`, `SKILL_FLEE`, `UNIT_CHAR`, `UNIT_PET`, `SKILL_SP_COST` (dict, copy nguyên).

Thay phần nạp file (`_load_pets`, `_load_skill_info`) để đọc từ Android assets thay vì `_base_dir()`:
```python
"""Ban rut gon cua bot/config.py cho Android Train-only: giu hang so + PET_SKILLS/
SKILL_INFO, BO ACCOUNTS/PARTY_CONFIG (Android quan ly account rieng qua Kotlin)."""
import json
from java import jclass

HEAL_HP_THRESHOLD = 0.70
HEAL_SP_COST = 42
PET_FIRE_MIN_SP = 65
CHAR_FIRE_MIN_SP = 65
SKILL_NORMAL = 10000
SKILL_ROCK = 10005
SKILL_FIRE = 12003
SKILL_HEAL_ALL = 11010
SKILL_HEAL_ONE = 11004
SKILL_DEFEND = 17001
SKILL_FLEE = 18001
UNIT_CHAR = 3
UNIT_PET = 2


def _read_asset(name: str) -> str:
    """Doc file text tu android assets/train_bot_data/ qua Context (truyen vao tu Kotlin
    luc Python.start(), hoac dung AndroidPlatform de lay context - xac nhan cach lay
    context trong Chaquopy khi viet code, xem vi du co san trong smoke_login/MainActivity)."""
    from com.chaquo.python import Python
    ctx = Python.getPlatform().getApplication()
    stream = ctx.getAssets().open(f"train_bot_data/{name}")
    data = bytes(stream.readAllBytes())
    stream.close()
    return data.decode("utf-8")


def _load_pets():
    raw = json.loads(_read_asset("pets.json"))
    skills, names, he_doanh = {}, {}, {}
    for pid_hex, info in raw.get("pets", {}).items():
        pid = int(pid_hex, 16)
        skills[pid] = info.get("skills", [])
        names[pid] = info.get("name", "")
        he_doanh[pid] = (info.get("he"), info.get("doanh"))
    return skills, names, he_doanh


PET_SKILLS, PET_NAMES, PET_HE_DOANH = _load_pets()


def _load_skill_info():
    raw = json.loads(_read_asset("skills_data.json"))
    return {int(k): v for k, v in raw.items()}


SKILL_INFO = _load_skill_info()
```
Ghi chú cho engineer: xác nhận đúng cấu trúc `pets.json`/`skills_data.json` bằng cách đọc `bot/config.py`'s `_load_pets`/`_load_skill_info` gốc (dòng 161-192) TRƯỚC khi viết bản Android — bản trên chỉ là khung, phải khớp CHÍNH XÁC cấu trúc JSON thật (đã biết `pets.json` có dạng `{"pets": {"0xXXXX": {"name", "skills", "he", "doanh"}}}` theo `CLAUDE.md`/ghi chú trong summary trước, xác nhận lại bằng cách mở file thật).

- [ ] **Step 2: Copy `bot/auth.py` → `train_bot/auth.py` nguyên vẹn**, chỉ đổi `from .protocol import xor, OP_LOGIN` thành `from .protocol import OP_LOGIN` và `from . import protocol` (dùng `protocol.encode` thay vì tự dựng frame + `xor`, vì XOR giờ nằm trong native — xem lại `build_auth_packet`, đổi:
```python
def build_auth_packet(user_id: str, access_token: str, server_id: int = 1) -> bytes:
    from . import protocol
    prefix = bytes([0x00, 0x00, 0x02, 0x01, server_id & 0xFF,
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x19, 0x14, 0x00])
    cred = (user_id + "f" + access_token).encode("utf-16-le")
    return protocol.encode(OP_LOGIN, prefix + cred)   # protocol.encode tu goi native (header+xor)
```
(Đây chính là logic đã viết đúng trong `smoke_login.py::build_auth_payload` — Task này CHUYỂN logic đó vào `train_bot/auth.py` để `client.py` dùng chung, tránh trùng lặp code giữa `smoke_login.py` cũ và bot mới.)

- [ ] **Step 3: Copy `bot/login.py` → `train_bot/login.py`**, xoá dòng `from . import config` + `username = username or config.USERNAME` (Android luôn truyền username/password tường minh, không có config mặc định) — giữ nguyên `API_KEY`, `LOGIN_URL`, `_device_id_for`, `_tracking_id_for`, toàn bộ `login()` (đã có bản đã port đúng trong `smoke_login.py::http_login` từ trước — copy logic đó, đổi tên hàm về `login()` cho khớp cách gọi gốc).

- [ ] **Step 4: Copy `bot/state.py` → `train_bot/state.py` NGUYÊN VẸN** (không phụ thuộc client/party, xác nhận lại bằng cách đọc toàn bộ 263 dòng trước khi copy — nếu có `import` nào trỏ tới `bot.xxx` khác, đổi thành `from . import xxx` cho khớp package `train_bot`).

- [ ] **Step 5: Copy `bot/combat.py` → `train_bot/combat.py` NGUYÊN VẸN** (tự chứa, chỉ cần đổi `from . import config` giữ nguyên vì đã có `train_bot/config.py` cùng tên hàm/hằng số cần dùng — kiểm tra combat.py có dùng hằng số nào KHÔNG có trong bản config rút gọn ở Step 1 thì bổ sung thêm vào `train_bot/config.py`).

- [ ] **Step 6: Copy `bot/client.py` → `train_bot/client.py`**, đọc toàn bộ file gốc rồi:
  - Đổi `from . import protocol` / `from .protocol import ...` giữ nguyên (dùng bản shim `train_bot/protocol.py` từ Task 2).
  - Tìm vòng lặp nhận dữ liệu (`_recv_loop` hoặc tương đương, dùng `sock.recv()` + `protocol.parse_stream`) — vì `train_bot/protocol.py::parse_stream` giờ nhận **raw wire (chưa xor)** thay vì **đã xor** (khác bản gốc), sửa đúng 1 chỗ: bỏ dòng gọi `protocol.xor(raw)` trước khi gọi `parse_stream`, truyền thẳng `raw` (bytes nhận từ socket) vào `parse_stream`.
  - GIỮ NGUYÊN toàn bộ phần còn lại: `GameClient.__init__`, `connect()`, `_login_setup()`, `_dispatch()`, `_on_actions`, `_make_decisions()`, `_arm_decision`, `_send_combat()`, `_on_pet_list()`, `use_item()`, `move_to()`, `start_run_around()`/`_run_around_loop()` — KHÔNG xoá code party/digioi/o5 dù không dùng tới (rủi ro sửa nhầm logic đang chạy đúng trên PC cao hơn lợi ích xoá code chết; các nhánh đó chỉ đơn giản không được gọi tới khi chạy solo train).
  - Xác nhận `GameClient.__init__` không bắt buộc tham số party nào (đã xác nhận qua đọc code: `party_idx`/`party_leader`/`party_members` optional, mặc định `None`/`[]`).

- [ ] **Step 7: Copy 2 file JSON tham chiếu vào assets**

```bash
mkdir -p android/app/src/main/assets/train_bot_data
cp pets.json android/app/src/main/assets/train_bot_data/
cp skills_data.json android/app/src/main/assets/train_bot_data/
```

- [ ] **Step 8: Viết test import-smoke đơn giản** — xác nhận toàn bộ package import được, không lỗi cú pháp/thiếu asset, TRƯỚC khi viết `train_runner.py` ở Task 4:

`android/app/src/androidTest/java/com/tsbot/android/TrainBotImportTest.kt`:
```kotlin
package com.tsbot.android

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.Assert.assertNotNull

@RunWith(AndroidJUnit4::class)
class TrainBotImportTest {
    @Before
    fun setup() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        if (!Python.isStarted()) Python.start(AndroidPlatform(ctx))
    }

    @Test
    fun importAllModulesNoError() {
        val py = Python.getInstance()
        assertNotNull(py.getModule("train_bot.config"))
        assertNotNull(py.getModule("train_bot.auth"))
        assertNotNull(py.getModule("train_bot.login"))
        assertNotNull(py.getModule("train_bot.state"))
        assertNotNull(py.getModule("train_bot.combat"))
        assertNotNull(py.getModule("train_bot.client"))
    }
}
```

Run: `./gradlew connectedDebugAndroidTest`, kiểm tra XML report `failures="0"`. Nếu lỗi import do thiếu hằng số trong `config.py` rút gọn, quay lại Step 1 bổ sung.

- [ ] **Step 9: Commit**

```bash
git add android/app/src/main/python/train_bot/ android/app/src/main/assets/train_bot_data/ \
        android/app/src/androidTest/java/com/tsbot/android/TrainBotImportTest.kt
git commit -m "feat(android): port bot/{config,auth,login,state,combat,client}.py vao train_bot/ package"
```

---

### Task 4: `train_runner.py` — vòng lặp chạy 1 account (mô phỏng `run_grind.py`)

**Files:**
- Create: `android/app/src/main/python/train_bot/train_runner.py`
- Test: `android/app/src/androidTest/java/com/tsbot/android/TrainRunnerTest.kt`

- [ ] **Step 1: Viết `train_runner.py`**

```python
"""Vong lap chay 1 account o mode Train - phong theo run_grind.py (PC), nhan
credentials truc tiep tu tham so (khong doc config.py), goi callback Kotlin de
bao trang thai (dung cho BotForegroundService cap nhat StateFlow)."""
import threading
import random
import struct
import time

from . import login as login_mod
from .client import GameClient

WANDER_POINTS = [(300, 250), (500, 400), (700, 500), (450, 300),
                  (250, 200), (600, 450), (400, 550), (650, 300)]


def run_train(username: str, password: str, server_ip: str, server_id: int,
              should_stop, on_status):
    """Chay den khi should_stop() tra True hoac loi khong the phuc hoi.
    on_status(state: str, hp, sp, hp_max, sp_max, message: str) goi moi khi trang
    thai doi (state: "connecting"|"running"|"error"|"stopped")."""
    on_status("connecting", None, None, None, None, "Dang dang nhap...")
    try:
        cred = login_mod.login(username, password)
    except Exception as e:
        on_status("error", None, None, None, None, f"Login loi: {e}")
        return

    try:
        c = GameClient(cred["user_id"], cred["access_token"], server_ip=server_ip,
                        server_id=server_id)
        c.connect()
    except Exception as e:
        on_status("error", None, None, None, None, f"Ket noi loi: {e}")
        return

    def wander():
        while c.running and not should_stop():
            if not c.in_combat():
                x, y = random.choice(WANDER_POINTS)
                try:
                    c.send(0x06, b"\x01\x00\x01" + struct.pack("<H", x) + struct.pack("<H", y))
                except OSError:
                    break
            time.sleep(2)

    threading.Thread(target=wander, daemon=True).start()
    on_status("running", None, None, None, None, "Da vao game, dang treo cay")

    while c.running and not should_stop():
        time.sleep(3)
        ch = c.state.char
        on_status("running", ch.hp, ch.sp, ch.hp_max, ch.sp_max, "")

    c.close()
    on_status("stopped", None, None, None, None, "Da dung")
```
Ghi chú cho engineer: xác nhận chữ ký thật của `GameClient.__init__` (tham số `server_ip`/`server_id` có thể tên khác trong `bot/client.py` gốc — đọc lại `GameClient.__init__` ở Task 3 Step 6 để khớp chính xác tên tham số, sửa lời gọi ở đây cho đúng).

- [ ] **Step 2: Viết instrumented test gọi thử `run_train` với server/tài khoản KHÔNG hợp lệ, xác nhận callback `on_status("error", ...)` được gọi thay vì crash**

```kotlin
package com.tsbot.android

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.chaquo.python.Python
import com.chaquo.python.PyObject
import com.chaquo.python.android.AndroidPlatform
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.Assert.assertEquals
import java.util.concurrent.atomic.AtomicReference

@RunWith(AndroidJUnit4::class)
class TrainRunnerTest {
    @Before
    fun setup() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        if (!Python.isStarted()) Python.start(AndroidPlatform(ctx))
    }

    @Test
    fun invalidLoginReportsErrorNotCrash() {
        val py = Python.getInstance()
        val mod = py.getModule("train_bot.train_runner")
        val lastState = AtomicReference<String>()
        val onStatus = PyObject.fromJava(object {
            fun call(state: String, hp: PyObject?, sp: PyObject?, hpMax: PyObject?, spMax: PyObject?, msg: String) {
                lastState.set(state)
            }
        })
        val shouldStop = PyObject.fromJava(object { fun call(): Boolean = false })
        mod.callAttr("run_train", "invalid_user_xyz", "wrong_pw", "1.2.3.4", 1, shouldStop, onStatus)
        assertEquals("error", lastState.get())
    }
}
```
Ghi chú: nếu Chaquopy không cho `PyObject.fromJava` với lambda kiểu này, dùng cách thay thế đã dùng ở `MainActivity.kt` hiện tại (gọi qua closure Kotlin thường, không cần proxy object phức tạp) — engineer tự điều chỉnh cách truyền callback Kotlin→Python cho khớp API Chaquopy thực tế (kiểm tra bằng build+run trước khi coi là xong).

- [ ] **Step 3: Build + chạy test, xác nhận qua XML report**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew connectedDebugAndroidTest
```

- [ ] **Step 4: Commit**

```bash
git add android/app/src/main/python/train_bot/train_runner.py \
        android/app/src/androidTest/java/com/tsbot/android/TrainRunnerTest.kt
git commit -m "feat(android): train_runner.py - vong lap solo train 1 account, bao trang thai qua callback"
```

---

### Task 5: Lưu trữ account (`AccountStore.kt`) + model trạng thái

**Files:**
- Create: `android/app/src/main/java/com/tsbot/android/Account.kt`
- Create: `android/app/src/main/java/com/tsbot/android/AccountStore.kt`
- Create: `android/app/src/main/java/com/tsbot/android/AccountStatus.kt`
- Test: `android/app/src/androidTest/java/com/tsbot/android/AccountStoreTest.kt`

- [ ] **Step 1: `Account.kt`**

```kotlin
package com.tsbot.android

data class Account(
    val username: String,
    val password: String,
    val serverKey: String,
)
```

- [ ] **Step 2: `AccountStatus.kt`**

```kotlin
package com.tsbot.android

enum class RunState { IDLE, CONNECTING, RUNNING, ERROR, STOPPED }

data class AccountStatus(
    val state: RunState = RunState.IDLE,
    val hp: Int? = null,
    val sp: Int? = null,
    val hpMax: Int? = null,
    val spMax: Int? = null,
    val message: String = "",
)
```

- [ ] **Step 3: `AccountStore.kt` — đọc/ghi `accounts.json` trong `filesDir`**

```kotlin
package com.tsbot.android

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

class AccountStore(private val context: Context) {
    private val file = File(context.filesDir, "accounts.json")

    fun load(): List<Account> {
        if (!file.exists()) return emptyList()
        val arr = JSONArray(file.readText())
        return (0 until arr.length()).map { i ->
            val o = arr.getJSONObject(i)
            Account(o.getString("username"), o.getString("password"), o.getString("server_key"))
        }
    }

    fun save(accounts: List<Account>) {
        val arr = JSONArray()
        accounts.forEach { a ->
            val o = JSONObject()
            o.put("username", a.username)
            o.put("password", a.password)
            o.put("server_key", a.serverKey)
            arr.put(o)
        }
        file.writeText(arr.toString())
    }

    fun add(account: Account) {
        val current = load().filterNot { it.username == account.username }
        save(current + account)
    }

    fun remove(username: String) {
        save(load().filterNot { it.username == username })
    }
}
```

- [ ] **Step 4: Test round-trip lưu/đọc**

`android/app/src/androidTest/java/com/tsbot/android/AccountStoreTest.kt`:
```kotlin
package com.tsbot.android

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.Assert.assertEquals

@RunWith(AndroidJUnit4::class)
class AccountStoreTest {
    @Test
    fun addThenLoadReturnsSameAccount() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val store = AccountStore(ctx)
        store.save(emptyList())
        store.add(Account("hoangt306", "pw123", "hoang_trung"))
        val loaded = store.load()
        assertEquals(1, loaded.size)
        assertEquals("hoangt306", loaded[0].username)
        assertEquals("hoang_trung", loaded[0].serverKey)
        store.save(emptyList())
    }

    @Test
    fun removeDeletesAccount() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val store = AccountStore(ctx)
        store.save(emptyList())
        store.add(Account("acc1", "pw", "trieu_van"))
        store.add(Account("acc2", "pw", "trieu_van"))
        store.remove("acc1")
        val loaded = store.load()
        assertEquals(1, loaded.size)
        assertEquals("acc2", loaded[0].username)
        store.save(emptyList())
    }
}
```

- [ ] **Step 5: Build + chạy test**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew connectedDebugAndroidTest
```
Xác nhận qua XML report.

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/java/com/tsbot/android/Account.kt \
        android/app/src/main/java/com/tsbot/android/AccountStore.kt \
        android/app/src/main/java/com/tsbot/android/AccountStatus.kt \
        android/app/src/androidTest/java/com/tsbot/android/AccountStoreTest.kt
git commit -m "feat(android): AccountStore doc/ghi accounts.json local, model Account/AccountStatus"
```

---

### Task 6: `BotForegroundService` — chạy nhiều account song song

**Files:**
- Create: `android/app/src/main/java/com/tsbot/android/BotForegroundService.kt`
- Modify: `android/app/src/main/AndroidManifest.xml`
- Test: `android/app/src/androidTest/java/com/tsbot/android/BotForegroundServiceTest.kt`

- [ ] **Step 1: Khai báo permission + service trong `AndroidManifest.xml`**

Thêm vào (giữ nguyên `INTERNET` đã có):
```xml
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
```
Trong `<application>`, thêm:
```xml
<service android:name=".BotForegroundService" android:exported="false" />
```

- [ ] **Step 2: `BotForegroundService.kt`**

```kotlin
package com.tsbot.android

import android.app.*
import android.content.Intent
import android.os.Binder
import android.os.Build
import android.os.IBinder
import com.chaquo.python.Python
import com.chaquo.python.PyObject
import com.chaquo.python.android.AndroidPlatform
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update

class BotForegroundService : Service() {
    private val binder = LocalBinder()
    private val runningThreads = mutableMapOf<String, Thread>()
    private val stopFlags = mutableMapOf<String, Boolean>()
    private val _status = MutableStateFlow<Map<String, AccountStatus>>(emptyMap())
    val status: StateFlow<Map<String, AccountStatus>> = _status

    inner class LocalBinder : Binder() {
        fun getService(): BotForegroundService = this@BotForegroundService
    }

    override fun onBind(intent: Intent): IBinder = binder

    override fun onCreate() {
        super.onCreate()
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
        startForeground(1, buildNotification())
    }

    private fun buildNotification(): Notification {
        val channelId = "tsbot_service"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(channelId, "TS Bot", NotificationManager.IMPORTANCE_LOW)
            (getSystemService(NotificationManager::class.java)).createNotificationChannel(channel)
        }
        return Notification.Builder(this, channelId)
            .setContentTitle("TS Bot đang chạy")
            .setSmallIcon(android.R.drawable.ic_media_play)
            .build()
    }

    fun startAccount(account: Account, serverIp: String, serverId: Int) {
        if (runningThreads.containsKey(account.username)) return
        stopFlags[account.username] = false
        val thread = Thread {
            try {
                val module = Python.getInstance().getModule("train_bot.train_runner")
                val shouldStop = PyObject.fromJava(object {
                    fun call(): Boolean = stopFlags[account.username] == true
                })
                val onStatus = PyObject.fromJava(object {
                    fun call(state: String, hp: PyObject?, sp: PyObject?, hpMax: PyObject?, spMax: PyObject?, msg: String) {
                        _status.update { it + (account.username to AccountStatus(
                            state = RunState.valueOf(state.uppercase()),
                            hp = hp?.toInt(), sp = sp?.toInt(), hpMax = hpMax?.toInt(), spMax = spMax?.toInt(),
                            message = msg,
                        )) }
                    }
                })
                module.callAttr("run_train", account.username, account.password, serverIp, serverId,
                    shouldStop, onStatus)
            } catch (e: Exception) {
                _status.update { it + (account.username to AccountStatus(RunState.ERROR, message = e.message ?: "loi khong ro")) }
            } finally {
                runningThreads.remove(account.username)
            }
        }
        runningThreads[account.username] = thread
        thread.start()
    }

    fun stopAccount(username: String) {
        stopFlags[username] = true
    }

    fun stopAll() {
        runningThreads.keys.toList().forEach { stopFlags[it] = true }
    }

    override fun onDestroy() {
        stopAll()
        super.onDestroy()
    }
}
```
Ghi chú cho engineer: xác nhận `PyObject.fromJava(object { fun call(...) })` là cách đúng để Chaquopy gọi ngược Kotlin→Python (nếu API thực tế khác, đây là điểm CẦN kiểm chứng bằng build+test thực tế — không suy đoán, sửa lại cho khớp API Chaquopy 16.0.0 thật khi build lỗi). Cần thêm dependency `androidx.core:core-ktx` cho `Flow` nếu chưa có trong `build.gradle.kts` — kiểm tra và bổ sung nếu thiếu.

- [ ] **Step 3: Test bind service + gọi `startAccount`/`stopAccount` với tài khoản KHÔNG hợp lệ, xác nhận `status` StateFlow chuyển sang ERROR (không crash)**

```kotlin
package com.tsbot.android

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.IBinder
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.Assert.assertEquals
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.flow.first

@RunWith(AndroidJUnit4::class)
class BotForegroundServiceTest {
    @Test
    fun invalidAccountReachesErrorState() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val latch = CountDownLatch(1)
        var boundService: BotForegroundService? = null
        val conn = object : ServiceConnection {
            override fun onServiceConnected(name: ComponentName, binder: IBinder) {
                boundService = (binder as BotForegroundService.LocalBinder).getService()
                latch.countDown()
            }
            override fun onServiceDisconnected(name: ComponentName) {}
        }
        val intent = Intent(ctx, BotForegroundService::class.java)
        ctx.bindService(intent, conn, Context.BIND_AUTO_CREATE)
        latch.await(10, TimeUnit.SECONDS)

        val svc = boundService!!
        svc.startAccount(Account("invalid_xyz", "wrong", "trieu_van"), "103.82.28.98", 1)

        var finalState: RunState? = null
        val deadline = System.currentTimeMillis() + 20000
        while (System.currentTimeMillis() < deadline) {
            val s = runBlocking { svc.status.first() }["invalid_xyz"]
            if (s?.state == RunState.ERROR) { finalState = s.state; break }
            Thread.sleep(500)
        }
        assertEquals(RunState.ERROR, finalState)
        ctx.unbindService(conn)
    }
}
```

- [ ] **Step 4: Build + chạy test trên thiết bị thật (cần mạng để chạm tới API login thật và nhận lỗi sai tài khoản)**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew connectedDebugAndroidTest
```
Xác nhận qua XML report `failures="0"`.

- [ ] **Step 5: Commit**

```bash
git add android/app/src/main/java/com/tsbot/android/BotForegroundService.kt \
        android/app/src/main/AndroidManifest.xml \
        android/app/src/androidTest/java/com/tsbot/android/BotForegroundServiceTest.kt
git commit -m "feat(android): BotForegroundService - chay nhieu account train song song, StateFlow trang thai"
```

---

### Task 7: `MainActivity` — danh sách account, thêm/xoá, start/stop, xem trạng thái

**Files:**
- Modify: `android/app/src/main/java/com/tsbot/android/MainActivity.kt`
- Modify: `android/app/build.gradle.kts` (thêm dependency Compose nếu chưa có)

- [ ] **Step 1: Kiểm tra `build.gradle.kts` đã có Compose chưa**

Nếu chưa, thêm (dùng phiên bản BOM ổn định thời điểm viết plan, engineer kiểm tra phiên bản mới nhất tương thích AGP 8.5/Kotlin 1.9.24 khi thực hiện):
```kotlin
buildFeatures { compose = true }
dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.06.00"))
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.0")
}
```

- [ ] **Step 2: Viết lại `MainActivity.kt`**

Thay toàn bộ nội dung hiện tại (form smoke-test login đơn) bằng: bind `BotForegroundService`, danh sách account từ `AccountStore`, mỗi dòng có nút Start/Stop + hiển thị `AccountStatus`, form thêm account mới (username/password/server spinner — tái dùng danh sách server từ `train_bot.config`-tương-đương hoặc hardcode `SERVERS` map giống `smoke_login.py` cũ, tránh phụ thuộc chéo — copy 13 server vào 1 hằng số Kotlin `object Servers { val ALL = listOf(...) }` để cả `MainActivity` và `BotForegroundService.startAccount` dùng chung IP/serverId theo `serverKey`).

Do khối lượng UI Compose khá dài (danh sách + form + dialog thêm account), engineer tự triển khai theo cấu trúc chuẩn Compose (`Scaffold` + `LazyColumn` cho danh sách account + `AlertDialog` cho form thêm account), dùng `collectAsState()` để bind `BotForegroundService.status` vào UI, theo đúng pattern đã dùng ở Task 6 cho service binding (bind trong `onServiceConnected`, lưu instance vào `mutableStateOf<BotForegroundService?>`).

- [ ] **Step 3: Test thủ công bằng ADB (không viết instrumented test cho toàn UI ở bước này — quá nhiều bề mặt, review bằng tay)**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew assembleDebug
```
Cài lại và kiểm tra bằng `adb install -r` + `uiautomator dump` (như đã làm ở các lần trước): xác nhận màn hình hiện danh sách account (ban đầu rỗng), có nút "Thêm account", sau khi thêm 1 account thấy xuất hiện trong danh sách kèm nút Start.

- [ ] **Step 4: Commit**

```bash
git add android/app/src/main/java/com/tsbot/android/MainActivity.kt android/app/build.gradle.kts
git commit -m "feat(android): MainActivity Compose UI - danh sach account, them/xoa, start/stop, xem trang thai"
```

---

### Task 8: Test tích hợp — 2 account chạy song song thật

**Files:**
- Test: `android/app/src/androidTest/java/com/tsbot/android/TwoAccountParallelTest.kt`

- [ ] **Step 1: Viết test dùng 2 tài khoản test thật (do người dùng cung cấp thủ công, KHÔNG hardcode mật khẩu thật vào file commit — đọc từ biến môi trường `adb shell setprop` hoặc file test-only `.gitignore`)**

Ghi chú cho engineer: đây là test CẦN 2 tài khoản game thật hợp lệ để chạy — không thể tự động hoá hoàn toàn nếu không có credentials thật. Best-effort: viết test SKIP nếu không tìm thấy file cấu hình test-credentials, và hướng dẫn trong comment cách người dùng tự chạy test này với tài khoản thật của họ (tạo file `android/app/src/androidTest/assets/test_accounts.json`, thêm vào `.gitignore`, đọc trong test — nếu file không tồn tại, `org.junit.Assume.assumeTrue(false)` để skip thay vì fail).

```kotlin
package com.tsbot.android

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.IBinder
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.Assert.assertEquals
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.flow.first

@RunWith(AndroidJUnit4::class)
class TwoAccountParallelTest {
    @Test
    fun twoAccountsRunConcurrentlyWithoutBlockingEachOther() {
        val ctx = InstrumentationRegistry.getInstrumentation().context
        val testAssets = try {
            JSONObject(ctx.assets.open("test_accounts.json").bufferedReader().readText())
        } catch (e: Exception) {
            null
        }
        assumeTrue("Can file android/app/src/androidTest/assets/test_accounts.json (xem huong dan trong plan) de chay test nay", testAssets != null)

        val acc1 = Account(testAssets!!.getJSONObject("acc1").getString("username"),
            testAssets.getJSONObject("acc1").getString("password"),
            testAssets.getJSONObject("acc1").getString("server_key"))
        val acc2 = Account(testAssets.getJSONObject("acc2").getString("username"),
            testAssets.getJSONObject("acc2").getString("password"),
            testAssets.getJSONObject("acc2").getString("server_key"))

        val targetCtx = InstrumentationRegistry.getInstrumentation().targetContext
        val latch = CountDownLatch(1)
        var svc: BotForegroundService? = null
        val conn = object : ServiceConnection {
            override fun onServiceConnected(name: ComponentName, binder: IBinder) {
                svc = (binder as BotForegroundService.LocalBinder).getService()
                latch.countDown()
            }
            override fun onServiceDisconnected(name: ComponentName) {}
        }
        targetCtx.bindService(Intent(targetCtx, BotForegroundService::class.java), conn, Context.BIND_AUTO_CREATE)
        latch.await(10, TimeUnit.SECONDS)

        svc!!.startAccount(acc1, Servers.ipFor(acc1.serverKey), Servers.idFor(acc1.serverKey))
        svc!!.startAccount(acc2, Servers.ipFor(acc2.serverKey), Servers.idFor(acc2.serverKey))

        val deadline = System.currentTimeMillis() + 30000
        var bothRunning = false
        while (System.currentTimeMillis() < deadline) {
            val statusMap = runBlocking { svc!!.status.first() }
            if (statusMap[acc1.username]?.state == RunState.RUNNING &&
                statusMap[acc2.username]?.state == RunState.RUNNING) {
                bothRunning = true
                break
            }
            Thread.sleep(1000)
        }
        assertEquals(true, bothRunning)
        svc!!.stopAccount(acc1.username)
        svc!!.stopAccount(acc2.username)
        targetCtx.unbindService(conn)
    }
}
```
(`Servers.ipFor`/`Servers.idFor` tham chiếu tới object `Servers` được tạo ở Task 7 Step 2 — nếu đặt tên khác lúc triển khai Task 7, sửa lại tên gọi ở đây cho khớp.)

- [ ] **Step 2: (Người dùng tự thực hiện, không phải engineer)** Tạo file `android/app/src/androidTest/assets/test_accounts.json` với 2 tài khoản test thật, thêm dòng vào `.gitignore`:
```
android/app/src/androidTest/assets/test_accounts.json
```

- [ ] **Step 3: Chạy test (nếu có file credentials) hoặc xác nhận SKIP gracefully (nếu không có)**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew connectedDebugAndroidTest
```
Kiểm tra XML report: test này `skipped="1"` nếu không có file credentials (chấp nhận được), hoặc `failures="0"` nếu có file và chạy thật.

- [ ] **Step 4: Commit**

```bash
git add android/app/src/androidTest/java/com/tsbot/android/TwoAccountParallelTest.kt .gitignore
git commit -m "test(android): tich hop 2 account train song song, SKIP gracefully neu thieu test credentials"
```

---

## Self-Review (đã thực hiện)

**1. Spec coverage:** Kiến trúc 1 Service/nhiều thread ✓ (Task 6), lưu JSON local ✓ (Task 5), giao tiếp StateFlow ✓ (Task 6), form Compose nhập trực tiếp ✓ (Task 7), port logic Train từ PC ✓ (Task 3-4), test chạy song song thật ✓ (Task 8). Phần "GIL/I/O-block" trong mục Rủi ro của spec được xác nhận thực tế qua Task 8 (2 account cùng RUNNING đồng thời, không thread nào chặn thread kia).

**2. Placeholder scan:** Đã loại các câu mơ hồ kiểu "viết UI phù hợp" — Task 7 Step 2 có mô tả cụ thể cấu trúc Compose dù không viết hết code (khối lượng lớn, chấp nhận được vì đây là phần UI thuần, ít rủi ro logic sai như phần combat/protocol).

**3. Type consistency:** `AccountStatus`/`RunState`/`Account` định nghĩa 1 lần ở Task 5, dùng nhất quán ở Task 6/7/8. `run_train(username, password, server_ip, server_id, should_stop, on_status)` chữ ký khớp giữa Task 4 (định nghĩa) và Task 6 (gọi).

## Execution Handoff

Plan hoàn chỉnh, lưu tại `docs/superpowers/plans/2026-07-02-android-service-foundation.md`. Hai lựa chọn thực thi:

1. **Subagent-Driven (khuyến nghị)** — dispatch subagent riêng cho từng Task, review 2 vòng (spec + code quality) sau mỗi task.
2. **Inline Execution** — thực thi tuần tự trong session này, có checkpoint sau mỗi task để anh xem/duyệt.

Anh muốn làm theo cách nào?
