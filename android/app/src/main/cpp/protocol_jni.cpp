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

    tsbot::DecodeResult r = tsbot::decodeStream(wire);

    jclass byteArrayClass = env->FindClass("[B");
    jobjectArray result = env->NewObjectArray(static_cast<jsize>(r.frames.size() + 1), byteArrayClass, nullptr);

    jbyteArray consumedArr = env->NewByteArray(4);
    jbyte consumedBytes[4] = {
        static_cast<jbyte>(r.consumed & 0xFF),
        static_cast<jbyte>((r.consumed >> 8) & 0xFF),
        static_cast<jbyte>((r.consumed >> 16) & 0xFF),
        static_cast<jbyte>((r.consumed >> 24) & 0xFF)
    };
    env->SetByteArrayRegion(consumedArr, 0, 4, consumedBytes);
    env->SetObjectArrayElement(result, 0, consumedArr);
    env->DeleteLocalRef(consumedArr);

    for (size_t i = 0; i < r.frames.size(); i++) {
        jbyteArray frameArr = env->NewByteArray(static_cast<jsize>(r.frames[i].size()));
        env->SetByteArrayRegion(frameArr, 0, static_cast<jsize>(r.frames[i].size()),
                                 reinterpret_cast<const jbyte*>(r.frames[i].data()));
        env->SetObjectArrayElement(result, static_cast<jsize>(i + 1), frameArr);
        env->DeleteLocalRef(frameArr);
    }
    return result;
}
