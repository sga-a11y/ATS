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
            break;
        }
        frames.emplace_back(plain.begin() + i, plain.begin() + i + len);
        i += len;
    }
    return frames;
}

}  // namespace tsbot
