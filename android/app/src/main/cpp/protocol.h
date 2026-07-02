#pragma once
#include <cstdint>
#include <vector>

namespace tsbot {

std::vector<uint8_t> encodeFrame(uint8_t opcode, const std::vector<uint8_t>& payload);
std::vector<std::vector<uint8_t>> decodeStream(const std::vector<uint8_t>& wireBuf);

}  // namespace tsbot
