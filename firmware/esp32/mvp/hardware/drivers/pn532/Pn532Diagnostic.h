#pragma once
#include <Wire.h>
#include <atomic>
#include "../../core/OgpassReader.h"

namespace ogpass {
// An I2C ACK is transport health only, not firmware or protocol verification.
class Pn532Diagnostic final : public OgpassReader {
    std::atomic<Health> state{Health::Disabled};
    bool enabled;
public:
    explicit Pn532Diagnostic(bool enabled=false):enabled(enabled){}
    const char* name() const override {return "pn532";}
    bool begin() override {
        if(!enabled) {state=Health::Disabled;return false;}
        if(!Wire.begin(21,22,100000)) {state=Health::ERROR;return false;}
        Wire.setTimeOut(40);
        Wire.beginTransmission(0x24);
        const uint8_t error=Wire.endTransmission();
        state=error==0 ? Health::CONNECTED : error==2 ? Health::OFFLINE : Health::ERROR;
        return state==Health::CONNECTED;
    }
    Health health() const override {return state.load();}
    bool detect() override {return false;}
    Result read(Detection&) override {return Result::UNSUPPORTED;}
    uint16_t capabilities() const override {return HEALTH;}
};
}
