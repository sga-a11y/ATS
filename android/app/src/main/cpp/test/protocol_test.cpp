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
    std::vector<uint8_t> payload(PLAINTEXT.begin() + 7, PLAINTEXT.end());
    auto wire = tsbot::encodeFrame(0x32, payload);
    assert(wire == WIRE_BYTES);
    printf("test_encode_roundtrip: PASS\n");
}

void test_decode_partial_stream_waits_for_more_bytes() {
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
