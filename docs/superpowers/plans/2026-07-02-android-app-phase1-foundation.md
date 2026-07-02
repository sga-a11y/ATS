# TS Online Bot — Android Phase 1: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng khung project Android (Gradle + Chaquopy + NDK/CMake) và chứng minh được 3 rủi ro
kỹ thuật lớn nhất trong spec chạy thật: (1) Chaquopy + NDK cùng tồn tại trong 1 project build được,
(2) protocol-native (C++) mã hoá/giải mã đúng frame game (kiểm chứng bằng dữ liệu capture thật),
(3) Python (qua Chaquopy) gọi được qua JNI vào code C++ đó và tạo/parse được gói tin thật.

**Architecture:** Xem `docs/superpowers/specs/2026-07-02-android-app-design.md`. Phase này chỉ dựng
tầng thấp nhất (`protocol-native` + cầu nối JNI + cầu nối Python) và 1 Foreground Service tối giản
để xác nhận luồng login thật hoạt động. UI (Compose), Overlay Bubble, port toàn bộ combat/party
logic sẽ là các plan riêng ở Phase 2+ (không nằm trong plan này — theo đúng spec mục "Không làm
trong v1" + để plan này ra được phần mềm test được độc lập trước).

**Tech Stack:** Kotlin, Android Gradle Plugin, Chaquopy Gradle plugin, Android NDK r26+ (CMake),
JNI, C++17, Jetpack Compose (chỉ 1 màn hình trắng để xác nhận app build/chạy được).

---

## Trước khi bắt đầu (môi trường)

Máy hiện tại **chưa có** Android Studio/SDK/NDK. Kỹ sư thực hiện plan này cần cài trước:
1. Android Studio (bản mới nhất, kèm Android SDK Platform 34+).
2. Trong SDK Manager: cài **NDK (Side by side)** phiên bản 26.x và **CMake** 3.22+.
3. Chaquopy yêu cầu Python 3.8-3.12 cài sẵn trên máy dev (dùng để build wheel lúc biên dịch, KHÔNG
   phải Python chạy trên điện thoại — Chaquopy tự bundle interpreter riêng vào APK).

Không cài xong 3 mục trên thì **không chạy được Task 1**.

## File Structure

```
android/                              <- THU MUC MOI, tach biet code Windows hien co
├── settings.gradle.kts
├── build.gradle.kts
├── gradle.properties
├── app/
│   ├── build.gradle.kts
│   ├── src/main/
│   │   ├── AndroidManifest.xml
│   │   ├── cpp/
│   │   │   ├── CMakeLists.txt
│   │   │   ├── protocol.h            <- khai bao ham C++ thuan (khong phu thuoc Android)
│   │   │   ├── protocol.cpp          <- XOR cipher + build/parse frame
│   │   │   ├── protocol_jni.cpp      <- lop JNI, expose sang Kotlin
│   │   │   └── test/
│   │   │       └── protocol_test.cpp <- test C++ thuan, bien dich CHAY TREN MAY DEV (khong can Android)
│   │   ├── java/com/tsbot/android/
│   │   │   ├── MainActivity.kt       <- 1 man hinh trang, xac nhan app chay
│   │   │   └── ProtocolBridge.kt     <- Kotlin wrapper goi JNI (external fun)
│   │   ├── python/
│   │   │   └── bot_native_bridge.py  <- Python goi Kotlin/JNI qua Chaquopy `java` module
│   │   └── androidTest/java/com/tsbot/android/
│   │       ├── ProtocolBridgeTest.kt <- instrumented test: Kotlin -> JNI round-trip
│   │       └── PythonBridgeTest.kt   <- instrumented test: Python -> JNI round-trip qua Chaquopy
```

---

### Task 1: Khung Gradle project + build rong chay duoc

**Files:**
- Create: `android/settings.gradle.kts`
- Create: `android/build.gradle.kts`
- Create: `android/gradle.properties`
- Create: `android/app/build.gradle.kts`
- Create: `android/app/src/main/AndroidManifest.xml`
- Create: `android/app/src/main/java/com/tsbot/android/MainActivity.kt`

- [ ] **Step 1: Tạo `android/settings.gradle.kts`**

```kotlin
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "TSBotAndroid"
include(":app")
```

- [ ] **Step 2: Tạo `android/build.gradle.kts`**

```kotlin
plugins {
    id("com.android.application") version "8.5.0" apply false
    id("org.jetbrains.kotlin.android") version "1.9.24" apply false
    id("com.chaquo.python") version "16.0.0" apply false
}
```

- [ ] **Step 3: Tạo `android/gradle.properties`**

```properties
android.useAndroidX=true
kotlin.code.style=official
org.gradle.jvmargs=-Xmx2048m
```

- [ ] **Step 4: Tạo `android/app/build.gradle.kts`**

```kotlin
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.tsbot.android"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.tsbot.android"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1-phase1"

        ndk {
            abiFilters += listOf("arm64-v8a", "armeabi-v7a")
        }
        externalNativeBuild {
            cmake {
                cppFlags += "-std=c++17"
            }
        }
        python {
            buildPython("python3")
            pyc {
                src = false   // KHONG dong goi .py source vao APK - chi giu bytecode (xem spec muc bao ve)
            }
        }
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.6.1")
}
```

- [ ] **Step 5: Tạo `android/app/src/main/AndroidManifest.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/auto">
    <uses-permission android:name="android.permission.INTERNET" />
    <application
        android:label="TS Bot (Phase1)"
        android:allowBackup="false">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

- [ ] **Step 6: Tạo `android/app/src/main/java/com/tsbot/android/MainActivity.kt`**

```kotlin
package com.tsbot.android

import android.os.Bundle
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val tv = TextView(this)
        tv.text = "TS Bot Android - Phase 1 (foundation)"
        setContentView(tv)
    }
}
```

- [ ] **Step 7: Build thử (chưa cần thiết bị)**

Run (từ thư mục `android/`): `./gradlew assembleDebug`
Expected: `BUILD SUCCESSFUL`, sinh ra file
`android/app/build/outputs/apk/debug/app-debug.apk`.

Nếu lỗi liên quan Chaquopy tìm không thấy Python: kiểm tra biến môi trường `PATH` có `python3`/
`python` trỏ đúng bản Python 3.8-3.12 đã cài ở bước "Trước khi bắt đầu".

- [ ] **Step 8: Commit**

```bash
git add android/settings.gradle.kts android/build.gradle.kts android/gradle.properties \
        android/app/build.gradle.kts android/app/src/main/AndroidManifest.xml \
        android/app/src/main/java/com/tsbot/android/MainActivity.kt
git commit -m "feat(android): khung Gradle project + Chaquopy plugin, build rong chay duoc"
```

---

### Task 2: protocol-native (C++ thuần) — XOR cipher + build/parse frame

Dùng lại đúng công thức đã xác nhận trong `bot/protocol.py` (XOR key `0xAD`, frame
`c0 91 [len2 LE] 00 00 [opcode] [payload]`, `len` = TỔNG độ dài frame). Vector test lấy từ 1 gói
C2S `0x32` (combat) đã capture + giải mã thật trong quá trình debug bot bản PC (frame plaintext
`c0 91 11 00 00 00 32 01 00 03 02 01 01 e3 2e 07 a9`), tính tay dạng "wire" (đã XOR 0xAD) để làm
input cho hàm `decode`.

**Files:**
- Create: `android/app/src/main/cpp/protocol.h`
- Create: `android/app/src/main/cpp/protocol.cpp`
- Create: `android/app/src/main/cpp/CMakeLists.txt`
- Create: `android/app/src/main/cpp/test/protocol_test.cpp`

- [ ] **Step 1: Viết test C++ (thất bại trước vì chưa có `protocol.cpp`)**

Tạo `android/app/src/main/cpp/test/protocol_test.cpp`:

```cpp
#include "../protocol.h"
#include <cassert>
#include <cstdio>
#include <vector>
#include <cstdint>

// Vector xac nhan tu capture that: plaintext frame (C2S 0x32) da xor 0xAD -> "wire bytes".
// plaintext: c0 91 11 00 00 00 32 01 00 03 02 01 01 e3 2e 07 a9
static std::vector<uint8_t> WIRE_BYTES = {
    0x6d, 0x3c, 0xbc, 0xad, 0xad, 0xad, 0x9f, 0xac,
    0xad, 0xae, 0xaf, 0xac, 0xac, 0x4e, 0x83, 0xaa, 0x04
};
static std::vector<uint8_t> PLAINTEXT = {
    0xc0, 0x91, 0x11, 0x00, 0x00, 0x00, 0x32, 0x01,
    0x00, 0x03, 0x02, 0x01, 0x01, 0xe3, 0x2e, 0x07, 0xa9
};

void test_decode_single_frame() {
    auto frames = tsbot::decodeStream(WIRE_BYTES);
    assert(frames.size() == 1);
    assert(frames[0] == PLAINTEXT);
    printf("test_decode_single_frame: PASS\n");
}

void test_encode_roundtrip() {
    // opcode = 0x32, payload = plaintext[7:] (moi thu sau byte opcode)
    std::vector<uint8_t> payload(PLAINTEXT.begin() + 7, PLAINTEXT.end());
    auto wire = tsbot::encodeFrame(0x32, payload);
    assert(wire == WIRE_BYTES);
    printf("test_encode_roundtrip: PASS\n");
}

void test_decode_partial_stream_waits_for_more_bytes() {
    // Chi dua 5 byte dau (chua du 1 frame) -> phai tra ve RONG, khong crash.
    std::vector<uint8_t> partial(WIRE_BYTES.begin(), WIRE_BYTES.begin() + 5);
    auto frames = tsbot::decodeStream(partial);
    assert(frames.empty());
    printf("test_decode_partial_stream_waits_for_more_bytes: PASS\n");
}

int main() {
    test_decode_single_frame();
    test_encode_roundtrip();
    test_decode_partial_stream_waits_for_more_bytes();
    printf("ALL PASS\n");
    return 0;
}
```

- [ ] **Step 2: Thử biên dịch test (phải LỖI vì chưa có `protocol.h`/`protocol.cpp`)**

Run: `g++ -std=c++17 -I android/app/src/main/cpp android/app/src/main/cpp/test/protocol_test.cpp -o /tmp/protocol_test`
Expected: lỗi biên dịch kiểu `fatal error: '../protocol.h' file not found` hoặc tương tự (Windows:
dùng `g++` từ MinGW nếu có, hoặc build trong WSL/Git Bash có sẵn `g++`).

- [ ] **Step 3: Viết `protocol.h`**

```cpp
#pragma once
#include <cstdint>
#include <vector>

namespace tsbot {

// Ma hoa 1 frame de gui: header c0 91 [len2 LE] 00 00 [opcode] [payload], roi XOR 0xAD TOAN BO
// (ke ca header) - dung dung cong thuc da xac nhan trong bot/protocol.py (encode()).
std::vector<uint8_t> encodeFrame(uint8_t opcode, const std::vector<uint8_t>& payload);

// Giai ma 1 doan buffer THO (da nhan tu socket, con nguyen XOR) thanh danh sach frame PLAINTEXT
// day du (bao gom header). Frame chua du byte thi BO QUA (doi lan goi sau, khong loi).
std::vector<std::vector<uint8_t>> decodeStream(const std::vector<uint8_t>& wireBuf);

}  // namespace tsbot
```

- [ ] **Step 4: Viết `protocol.cpp`**

```cpp
#include "protocol.h"

namespace tsbot {

constexpr uint8_t XOR_KEY = 0xAD;

static std::vector<uint8_t> xorBytes(const std::vector<uint8_t>& in) {
    std::vector<uint8_t> out(in.size());
    for (size_t i = 0; i < in.size(); i++) {
        out[i] = in[i] ^ XOR_KEY;
    }
    return out;
}

std::vector<uint8_t> encodeFrame(uint8_t opcode, const std::vector<uint8_t>& payload) {
    // header: c0 91 [len2 LE] 00 00 [opcode]  (7 byte) + payload
    uint16_t totalLen = static_cast<uint16_t>(7 + payload.size());
    std::vector<uint8_t> plain;
    plain.reserve(totalLen);
    plain.push_back(0xc0);
    plain.push_back(0x91);
    plain.push_back(static_cast<uint8_t>(totalLen & 0xFF));
    plain.push_back(static_cast<uint8_t>((totalLen >> 8) & 0xFF));
    plain.push_back(0x00);
    plain.push_back(0x00);
    plain.push_back(opcode);
    plain.insert(plain.end(), payload.begin(), payload.end());
    return xorBytes(plain);
}

std::vector<std::vector<uint8_t>> decodeStream(const std::vector<uint8_t>& wireBuf) {
    std::vector<uint8_t> plain = xorBytes(wireBuf);
    std::vector<std::vector<uint8_t>> frames;
    size_t i = 0;
    while (i + 4 <= plain.size()) {
        if (plain[i] != 0xc0 || plain[i + 1] != 0x91) {
            i++;
            continue;
        }
        uint16_t len = static_cast<uint16_t>(plain[i + 2]) | (static_cast<uint16_t>(plain[i + 3]) << 8);
        if (len < 7 || i + len > plain.size()) {
            break;   // frame chua nhan du - doi lan sau
        }
        frames.emplace_back(plain.begin() + i, plain.begin() + i + len);
        i += len;
    }
    return frames;
}

}  // namespace tsbot
```

- [ ] **Step 5: Biên dịch + chạy test, xác nhận PASS**

Run: `g++ -std=c++17 -I android/app/src/main/cpp android/app/src/main/cpp/test/protocol_test.cpp android/app/src/main/cpp/protocol.cpp -o /tmp/protocol_test && /tmp/protocol_test`
Expected output:
```
test_decode_single_frame: PASS
test_encode_roundtrip: PASS
test_decode_partial_stream_waits_for_more_bytes: PASS
ALL PASS
```

- [ ] **Step 6: Tạo `CMakeLists.txt` (để NDK build ra `.so` dùng ở Task 3)**

```cmake
cmake_minimum_required(VERSION 3.22.1)
project(tsbot_protocol)

add_library(tsbot_protocol SHARED
    protocol.cpp
    protocol_jni.cpp
)

find_library(log-lib log)
target_link_libraries(tsbot_protocol ${log-lib})
target_compile_features(tsbot_protocol PUBLIC cxx_std_17)
```

(File `protocol_jni.cpp` được tạo ở Task 3 — CMake sẽ báo lỗi thiếu file nếu build ngay bây giờ,
đó là bình thường, chưa cần `./gradlew assembleDebug` lại ở task này.)

- [ ] **Step 7: Commit**

```bash
git add android/app/src/main/cpp/protocol.h android/app/src/main/cpp/protocol.cpp \
        android/app/src/main/cpp/test/protocol_test.cpp android/app/src/main/cpp/CMakeLists.txt
git commit -m "feat(android): protocol-native C++ (XOR cipher + frame encode/decode) voi test tren host"
```

---

### Task 3: JNI bridge (Kotlin ↔ C++)

**Files:**
- Create: `android/app/src/main/cpp/protocol_jni.cpp`
- Create: `android/app/src/main/java/com/tsbot/android/ProtocolBridge.kt`
- Create: `android/app/src/main/androidTest/java/com/tsbot/android/ProtocolBridgeTest.kt`

- [ ] **Step 1: Viết instrumented test trước (sẽ FAIL vì chưa có `ProtocolBridge`)**

Tạo `android/app/src/main/androidTest/java/com/tsbot/android/ProtocolBridgeTest.kt`:

```kotlin
package com.tsbot.android

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertArrayEquals
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ProtocolBridgeTest {

    private val wireBytes = byteArrayOf(
        0x6d.toByte(), 0x3c, 0xbc.toByte(), 0xad.toByte(), 0xad.toByte(), 0xad.toByte(),
        0x9f.toByte(), 0xac.toByte(), 0xad.toByte(), 0xae.toByte(), 0xaf.toByte(),
        0xac.toByte(), 0xac.toByte(), 0x4e, 0x83.toByte(), 0xaa.toByte(), 0x04
    )
    private val plaintext = byteArrayOf(
        0xc0.toByte(), 0x91.toByte(), 0x11, 0x00, 0x00, 0x00, 0x32, 0x01,
        0x00, 0x03, 0x02, 0x01, 0x01, 0xe3.toByte(), 0x2e, 0x07, 0xa9.toByte()
    )

    @Test
    fun decodeStream_parsesSingleFrame() {
        val frames = ProtocolBridge.decodeStream(wireBytes)
        assertArrayEquals(arrayOf(plaintext.toList()), frames.map { it.toList() }.toTypedArray())
    }

    @Test
    fun encodeFrame_matchesKnownWireBytes() {
        val payload = plaintext.copyOfRange(7, plaintext.size)
        val encoded = ProtocolBridge.encodeFrame(0x32, payload)
        assertArrayEquals(wireBytes, encoded)
    }
}
```

- [ ] **Step 2: Viết `protocol_jni.cpp`**

```cpp
#include <jni.h>
#include <vector>
#include "protocol.h"

extern "C" JNIEXPORT jbyteArray JNICALL
Java_com_tsbot_android_ProtocolBridge_nativeEncodeFrame(
        JNIEnv* env, jobject /*thiz*/, jint opcode, jbyteArray payloadArr) {
    jsize len = env->GetArrayLength(payloadArr);
    std::vector<uint8_t> payload(len);
    env->GetByteArrayRegion(payloadArr, 0, len, reinterpret_cast<jbyte*>(payload.data()));

    auto wire = tsbot::encodeFrame(static_cast<uint8_t>(opcode), payload);

    jbyteArray result = env->NewByteArray(static_cast<jsize>(wire.size()));
    env->SetByteArrayRegion(result, 0, static_cast<jsize>(wire.size()),
                             reinterpret_cast<const jbyte*>(wire.data()));
    return result;
}

extern "C" JNIEXPORT jobjectArray JNICALL
Java_com_tsbot_android_ProtocolBridge_nativeDecodeStream(
        JNIEnv* env, jobject /*thiz*/, jbyteArray wireArr) {
    jsize len = env->GetArrayLength(wireArr);
    std::vector<uint8_t> wire(len);
    env->GetByteArrayRegion(wireArr, 0, len, reinterpret_cast<jbyte*>(wire.data()));

    auto frames = tsbot::decodeStream(wire);

    jclass byteArrayClass = env->FindClass("[B");
    jobjectArray result = env->NewObjectArray(static_cast<jsize>(frames.size()), byteArrayClass, nullptr);
    for (size_t i = 0; i < frames.size(); i++) {
        jbyteArray frameArr = env->NewByteArray(static_cast<jsize>(frames[i].size()));
        env->SetByteArrayRegion(frameArr, 0, static_cast<jsize>(frames[i].size()),
                                 reinterpret_cast<const jbyte*>(frames[i].data()));
        env->SetObjectArrayElement(result, static_cast<jsize>(i), frameArr);
        env->DeleteLocalRef(frameArr);
    }
    return result;
}
```

- [ ] **Step 3: Viết `ProtocolBridge.kt`**

```kotlin
package com.tsbot.android

object ProtocolBridge {
    init {
        System.loadLibrary("tsbot_protocol")
    }

    private external fun nativeEncodeFrame(opcode: Int, payload: ByteArray): ByteArray
    private external fun nativeDecodeStream(wire: ByteArray): Array<ByteArray>

    fun encodeFrame(opcode: Int, payload: ByteArray): ByteArray = nativeEncodeFrame(opcode, payload)
    fun decodeStream(wire: ByteArray): List<ByteArray> = nativeDecodeStream(wire).toList()
}
```

- [ ] **Step 4: Build + chạy instrumented test trên thiết bị/emulator đã kết nối**

Run (từ `android/`): `./gradlew connectedDebugAndroidTest --tests "com.tsbot.android.ProtocolBridgeTest"`
Expected: `BUILD SUCCESSFUL`, 2 test PASS (`decodeStream_parsesSingleFrame`,
`encodeFrame_matchesKnownWireBytes`).

Yêu cầu: có 1 thiết bị Android that hoặc emulator đang chạy (`adb devices` phải thấy ít nhất 1
dòng `device`).

- [ ] **Step 5: Commit**

```bash
git add android/app/src/main/cpp/protocol_jni.cpp android/app/src/main/java/com/tsbot/android/ProtocolBridge.kt \
        android/app/src/main/androidTest/java/com/tsbot/android/ProtocolBridgeTest.kt
git commit -m "feat(android): JNI bridge Kotlin<->C++ cho protocol-native, xac nhan bang instrumented test"
```

---

### Task 4: Python (Chaquopy) gọi được qua JNI bridge

**Files:**
- Create: `android/app/src/main/python/bot_native_bridge.py`
- Create: `android/app/src/main/androidTest/java/com/tsbot/android/PythonBridgeTest.kt`

- [ ] **Step 1: Viết instrumented test trước (FAIL vì chưa có module Python)**

Tạo `android/app/src/main/androidTest/java/com/tsbot/android/PythonBridgeTest.kt`:

```kotlin
package com.tsbot.android

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Assert.assertArrayEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class PythonBridgeTest {

    @Before
    fun setUp() {
        if (!Python.isStarted()) {
            val ctx = InstrumentationRegistry.getInstrumentation().targetContext
            Python.start(AndroidPlatform(ctx))
        }
    }

    @Test
    fun pythonEncodeFrame_matchesNativeResult() {
        val py = Python.getInstance()
        val module = py.getModule("bot_native_bridge")
        val payload = byteArrayOf(0x01, 0x00, 0x03, 0x02, 0x01, 0x01, 0xe3.toByte(), 0x2e, 0x07, 0xa9.toByte())
        val fromPython = module.callAttr("encode_frame", 0x32, payload).toJava(ByteArray::class.java)
        val fromKotlin = ProtocolBridge.encodeFrame(0x32, payload)
        assertArrayEquals(fromKotlin, fromPython)
    }
}
```

- [ ] **Step 2: Viết `bot_native_bridge.py`**

```python
"""Cau noi Python (Chaquopy) -> protocol-native (C++) qua JNI. Python KHONG tu lam XOR/frame
nua - moi thu di qua ProtocolBridge (Kotlin) de mac dinh dung 1 nguon that duy nhat, tranh
lech logic giua 2 ngon ngu (da xac nhan trong spec: day la lop bao ve chinh cho giao thuc)."""
from java import jclass


def _bridge():
    return jclass("com.tsbot.android.ProtocolBridge")


def encode_frame(opcode: int, payload: bytes) -> bytes:
    result = _bridge().INSTANCE.encodeFrame(opcode, payload)
    return bytes(result)


def decode_stream(wire_buf: bytes):
    result = _bridge().INSTANCE.decodeStream(wire_buf)
    return [bytes(f) for f in result]
```

Lưu ý: `ProtocolBridge` ở Kotlin hiện là `object` (Kotlin singleton) — Chaquopy truy cập qua
`INSTANCE`. Nếu `jclass(...).INSTANCE` báo lỗi không tìm thấy field, đổi `ProtocolBridge` sang
class thường + companion object có `@JvmStatic`, cập nhật lại Step 2 và `ProtocolBridge.kt` cho
khớp trước khi chạy lại test.

- [ ] **Step 3: Build + chạy test**

Run: `./gradlew connectedDebugAndroidTest --tests "com.tsbot.android.PythonBridgeTest"`
Expected: `BUILD SUCCESSFUL`, test `pythonEncodeFrame_matchesNativeResult` PASS.

- [ ] **Step 4: Commit**

```bash
git add android/app/src/main/python/bot_native_bridge.py \
        android/app/src/main/androidTest/java/com/tsbot/android/PythonBridgeTest.kt
git commit -m "feat(android): Python (Chaquopy) goi duoc protocol-native qua JNI, xac nhan bang test"
```

---

### Task 5: Xác nhận thủ công — login thật tới server game

Task này **không tự động hoá** (không hardcode tài khoản thật vào code/test), vì không được commit
credential thật lên git và không nên tự động hit server game thật trong CI. Đây là bước xác nhận
tay 1 lần để chốt Phase 1 thực sự hoạt động end-to-end trước khi làm tiếp Phase 2 (UI/port toàn bộ
logic).

**Files:**
- Create: `android/app/src/main/python/smoke_login.py`
- Modify: `android/app/src/main/java/com/tsbot/android/MainActivity.kt`

- [ ] **Step 1: Copy hàm build gói auth từ bot PC (không sửa logic)**

Đọc `E:\Claude\ATS\bot\auth.py` và `E:\Claude\ATS\bot\protocol.py` (hàm `build_auth_packet`,
`XOR_KEY`) — copy nguyên logic build payload (KHÔNG copy phần `encode()`/`xor()` vì phần đó giờ
nằm ở native, gọi qua `bot_native_bridge`).

- [ ] **Step 2: Viết `smoke_login.py`**

```python
"""Xac nhan THU CONG (khong chay trong CI): mo socket that toi server game, gui goi auth qua
protocol-native, doc phan hoi dau tien, in ra Logcat. Sua GAME_HOST/PORT/USER_ID/TOKEN thanh gia
tri that (tu bot PC, xem bot/config.py + dang nhap qua bot/login.py de lay access_token) truoc
khi chay tay - KHONG commit gia tri that vao file nay."""
import socket
import bot_native_bridge as bridge

GAME_HOST = "CHANGE_ME"   # vd 103.82.28.98 - dien tay, khong commit
GAME_PORT = 6614
USER_ID = 0                # dien tay tu ket qua bot/login.py
ACCESS_TOKEN = "CHANGE_ME"  # dien tay


def build_auth_payload(user_id: int, access_token: str, server_id: int) -> bytes:
    # Port dung logic tu bot/auth.py:build_auth_packet - xem file do de doi chieu format that.
    import struct
    tok = access_token.encode("utf-8")
    return struct.pack("<I", user_id) + struct.pack("<H", len(tok)) + tok + struct.pack("<H", server_id)


def run_smoke_test():
    sock = socket.create_connection((GAME_HOST, GAME_PORT), timeout=15)
    payload = build_auth_payload(USER_ID, ACCESS_TOKEN, server_id=1)
    frame = bridge.encode_frame(0x01, payload)   # 0x01 = OP_LOGIN, xem bot/protocol.py
    sock.sendall(frame)
    raw = sock.recv(4096)
    frames = bridge.decode_stream(raw)
    print(f"[smoke_login] nhan {len(frames)} frame, frame dau: {frames[0].hex() if frames else None}")
    sock.close()
    return len(frames) > 0
```

- [ ] **Step 3: Gọi từ `MainActivity` qua 1 nút bấm tạm thời**

Sửa `android/app/src/main/java/com/tsbot/android/MainActivity.kt`:

```kotlin
package com.tsbot.android

import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlin.concurrent.thread

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
        val status = TextView(this)
        status.text = "TS Bot Android - Phase 1 (foundation)"
        val btn = Button(this)
        btn.text = "Smoke test login (xem Logcat)"
        btn.setOnClickListener {
            thread {
                val module = Python.getInstance().getModule("smoke_login")
                val ok = module.callAttr("run_smoke_test").toBoolean()
                runOnUiThread { status.text = "Smoke test: ${if (ok) "OK - nhan duoc frame" else "THAT BAI"}" }
            }
        }
        val layout = LinearLayout(this)
        layout.orientation = LinearLayout.VERTICAL
        layout.addView(status)
        layout.addView(btn)
        setContentView(layout)
    }
}
```

- [ ] **Step 4: Chạy tay trên thiết bị thật**

1. Mở `smoke_login.py`, điền `GAME_HOST`/`USER_ID`/`ACCESS_TOKEN` thật (lấy `access_token` bằng
   cách chạy `python -c "from bot.login import login; print(login('USERNAME','PASSWORD'))"` từ
   thư mục gốc `E:\Claude\ATS` trên máy PC).
2. Run: `./gradlew installDebug` (từ `android/`), mở app trên điện thoại, bấm nút "Smoke test
   login".
3. Xem log: `adb logcat | grep smoke_login`
   Expected: dòng `[smoke_login] nhan 1 frame, frame dau: c091...` (ít nhất 1 frame, không lỗi
   socket/timeout).
4. **Sau khi xác nhận xong, XOÁ giá trị thật khỏi `smoke_login.py`** (trả về `"CHANGE_ME"`) trước
   khi commit — không để lộ token thật lên git.

- [ ] **Step 5: Commit (sau khi đã xoá credential thật khỏi file)**

```bash
git add android/app/src/main/python/smoke_login.py android/app/src/main/java/com/tsbot/android/MainActivity.kt
git commit -m "feat(android): smoke test thu cong xac nhan login that qua protocol-native (Phase 1 hoan tat)"
```

---

## Self-Review (đã thực hiện)

1. **Spec coverage:** Task 1-4 kiểm chứng đúng 3 rủi ro nêu trong spec (mục "Rủi ro / điều cần xác
   nhận"): Chaquopy+NDK cùng build (Task 1), protocol-native đúng với dữ liệu capture thật
   (Task 2), JNI + Chaquopy gọi thông (Task 3-4). Task 5 xác nhận end-to-end với server thật.
   Phần UI/Overlay/port toàn bộ combat logic **cố ý để ngoài phạm vi plan này** (ghi rõ ở đầu
   file) — sẽ là plan riêng "Phase 2" sau khi Phase 1 được xác nhận chạy ổn.
2. **Placeholder scan:** Không còn "TBD/TODO" — riêng `smoke_login.py` có `CHANGE_ME` nhưng đây là
   CHỦ Ý (chỗ điền credential thật lúc chạy tay, không phải placeholder thiếu thiết kế).
3. **Type consistency:** `ProtocolBridge.encodeFrame(Int, ByteArray): ByteArray` và
   `decodeStream(ByteArray): List<ByteArray>` dùng nhất quán từ Task 3 (Kotlin) sang Task 4
   (Python wrapper) sang Task 5 (gọi từ `smoke_login.py`).
