// SPDX-License-Identifier: Apache-2.0
// Exercise the real XPCU encoder/decoder with an FX2 USB protocol model.
// This is software protocol evidence, not a connected-cable test.
#include <cassert>
#include <cstring>
#include <iostream>
#include <vector>

#include "xilinxPlatformCableUSB.hpp"

namespace {
std::vector<uint8_t> expected_tms, expected_tdi;
uint32_t position = 0, operations = 0, packet_start = 0;
bool capture = false, fail_write = false;
bool answer(uint32_t bit) { return ((bit * 17 + bit / 7 + 3) % 13) < 6; }
bool bit(const std::vector<uint8_t> &v, uint32_t i) { return (v[i >> 3] >> (i & 7)) & 1; }
}

FX2_ll::FX2_ll(uint16_t, uint16_t, uint16_t, uint16_t, const std::string &, int8_t) {}
FX2_ll::~FX2_ll() {}
bool FX2_ll::set_interface_alt_setting(int, int) { return true; }
int FX2_ll::write_ctrl(uint8_t req, uint16_t value, uint8_t *, uint16_t, uint16_t index)
{
    assert(req == 0xb0);
    if (value == 0xa6)
        operations = uint32_t(index) + 1;
    return 1;
}
int FX2_ll::read_ctrl(uint8_t, uint16_t value, uint8_t *buf, uint16_t len, uint16_t)
{
    std::memset(buf, 0, len);
    if (value == 0x38)
        buf[0] = 0x40;
    return 1;
}
int FX2_ll::write(uint8_t endpoint, uint8_t *buf, uint16_t len)
{
    assert(endpoint == 2);
    if (fail_write)
        return -1;
    assert(len == ((operations + 3) / 4) * 2);
    capture = (buf[1] & 0x10) != 0;
    packet_start = position;
    for (uint32_t i = 0; i < operations; ++i) {
        const uint32_t base = (i / 4) * 2, slot = i % 4;
        assert((buf[base + 1] >> slot) & 1); // Every operation clocks TCK.
        assert(bool((buf[base + 1] >> (slot + 4)) & 1) == capture);
        if (capture) {
            assert(bool((buf[base] >> slot) & 1) == bit(expected_tdi, position));
            assert(bool((buf[base] >> (slot + 4)) & 1) == bit(expected_tms, position));
            ++position;
        }
    }
    return len;
}
int FX2_ll::read(uint8_t endpoint, uint8_t *buf, uint16_t len)
{
    assert(endpoint == 0x86 && capture);
    // FX2 returns groups of 32 samples, left justified in a 16/32-bit
    // little-endian shift register for the final incomplete group.
    uint32_t consumed = 0, bytes = 0;
    while (consumed < operations) {
        const uint32_t group = std::min(uint32_t(32), operations - consumed);
        const uint32_t width = group > 16 ? 32 : 16;
        uint32_t value = 0;
        for (uint32_t k = 0; k < group; ++k)
            if (answer(packet_start + consumed + k))
                value |= 1u << (width - group + k);
        for (uint32_t k = 0; k < width / 8; ++k)
            buf[bytes++] = uint8_t(value >> (8 * k));
        consumed += group;
    }
    assert(bytes == len);
    return len;
}

int main()
{
    XilinxPlatformCableUSB cable(0x03fd, 0x0013, 6000000, "protocol-model.hex");
    for (uint32_t bits : {1u, 7u, 8u, 12u, 15u, 16u, 17u, 31u, 32u, 33u, 64u,
                          645u, 646u, 8191u, 8192u, 16393u}) {
        expected_tms.assign((bits + 7) / 8, 0);
        expected_tdi.assign((bits + 7) / 8, 0);
        std::vector<uint8_t> received((bits + 7) / 8, 0xff);
        for (uint32_t i = 0; i < bits; ++i) {
            if ((i % 5) < 2) expected_tms[i >> 3] |= 1u << (i & 7);
            if ((i % 7) < 3) expected_tdi[i >> 3] |= 1u << (i & 7);
        }
        // A previously buffered non-capture operation must flush separately.
        uint8_t pending = 0x03;
        assert(cable.writeTMS(&pending, 3, false, 1) == 3);
        position = 0;
        assert(cable.writeTMSTDI(expected_tms.data(), expected_tdi.data(), received.data(), bits));
        assert(position == bits);
        for (uint32_t i = 0; i < bits; ++i)
            assert(bit(received, i) == answer(i));
        if (bits % 8)
            assert((received.back() >> (bits % 8)) == 0);
    }
    assert(cable.writeTMSTDI(nullptr, nullptr, nullptr, 0));
    assert(!cable.writeTMSTDI(nullptr, expected_tdi.data(), expected_tms.data(), 1));
    fail_write = true;
    uint8_t zero = 0, result = 0;
    assert(!cable.writeTMSTDI(&zero, &zero, &result, 1));
    std::cout << "PASS: XPCU mixed TMS/TDI, partial bytes, 640-bit mailbox, multi-buffer reads and USB failure\n";
}
