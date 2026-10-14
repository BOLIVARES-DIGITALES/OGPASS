#pragma once
#include <array>
#include <cstdint>
#include <cstddef>

namespace ogpass {
// Manufacturer data: Apple company ID, iBeacon prefix, UUID, major/minor, power.
inline std::array<uint8_t,25> beaconPayload(const std::array<uint8_t,16>& uuid,
                                          uint16_t major, uint16_t minor, int8_t power) {
    std::array<uint8_t,25> data{{0x4c,0x00,0x02,0x15}};
    for(size_t i=0;i<16;i++) data[i+4]=uuid[i];
    data[20]=major>>8;data[21]=major&0xff;
    data[22]=minor>>8;data[23]=minor&0xff;data[24]=static_cast<uint8_t>(power);
    return data;
}
}
