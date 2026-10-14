#pragma once
#include <cstdint>
#include <cstddef>

namespace ogpass {
enum class Health : uint8_t { CONNECTED, OFFLINE, ERROR, Disabled };
enum class Role : uint8_t { PRIMARY, OPTIONAL, RADIO };
enum Capability : uint16_t {
    IDENTIFY=1, READ=2, WRITE=4, AUTH=8, EMULATE=16, NDEF=32,
    APDU=64, BEACON=128, PROXIMITY=256, HEALTH=512
};
enum class Result : uint8_t { OK, NO_SIGNAL, UNSUPPORTED, ERROR };
struct Detection {
    char reader[16]{};
    char technology[16]{};
    char protocol[24]{};
    char uid[24]{};
    char type[48]{};
    uint8_t sak=0;
    uint16_t atqa=0;
    uint32_t latencyMs=0;
};
inline const char* healthName(Health state) {
    switch(state) {
        case Health::CONNECTED:return "CONNECTED";
        case Health::OFFLINE:return "OFFLINE";
        case Health::ERROR:return "ERROR";
        default:return "DISABLED";
    }
}
class OgpassReader {
public:
    virtual ~OgpassReader() = default;
    virtual const char* name() const = 0;
    virtual bool begin() = 0;
    virtual Health health() const = 0;
    virtual bool detect() = 0;
    virtual Result read(Detection&) = 0;
    virtual Result write(const uint8_t*, size_t) { return Result::UNSUPPORTED; }
    virtual Result emulate(const uint8_t*, size_t) { return Result::UNSUPPORTED; }
    virtual uint16_t capabilities() const = 0;
    virtual bool reset() { return begin(); }
};
}
