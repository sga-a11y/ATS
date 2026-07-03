#pragma once
#include <cstdint>
#include <vector>

namespace tsbot {

struct DecodeResult {
    std::vector<std::vector<uint8_t>> frames;
    size_t consumed;   // so byte cua wireBuf da duoc xu ly (frame hoan chinh); phan con lai la du lieu chua du
};

std::vector<uint8_t> encodeFrame(uint8_t opcode, const std::vector<uint8_t>& payload);
DecodeResult decodeStream(const std::vector<uint8_t>& wireBuf);

}  // namespace tsbot
