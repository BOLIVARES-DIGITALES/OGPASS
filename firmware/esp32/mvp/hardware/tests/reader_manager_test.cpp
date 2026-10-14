#include <cassert>
#include <cstring>
#include <iostream>
#include "../core/ReaderManager.h"
#include "../drivers/ble/BeaconPayload.h"
using namespace ogpass;
class Fake : public OgpassReader {
public:
    bool failing=false, begun=false, signal=true;
    int calls=0;
    const char* name() const override {return "fake";}
    bool begin() override {begun=true;return !failing;}
    Health health() const override {return failing?Health::ERROR:Health::CONNECTED;}
    bool detect() override {++calls;return signal;}
    Result read(Detection& out) override {strcpy(out.uid,"11223344");return Result::OK;}
    uint16_t capabilities() const override {return IDENTIFY|READ|HEALTH;}
};
int main() {
    ReaderManager manager;Fake primary,optional;
    optional.failing=true;
    assert(manager.add(primary,Role::PRIMARY));assert(manager.add(optional,Role::OPTIONAL));
    assert(!manager.add(primary,Role::PRIMARY));
    manager.beginPrimary();assert(primary.begun);assert(!optional.begun);
    Detection event;
    for(int i=0;i<1000;i++) assert(manager.pollPrimary(event));
    assert(optional.calls==0);assert(!optional.begun);
    manager.beginOptional();assert(optional.begun);
    assert(manager.pollPrimary(event));assert(!manager.pollOptional(event));
    primary.failing=true;optional.failing=false;
    assert(!manager.pollPrimary(event));assert(manager.pollOptional(event));
    assert(primary.write(nullptr,0)==Result::UNSUPPORTED);
    assert(primary.emulate(nullptr,0)==Result::UNSUPPORTED);
    std::array<uint8_t,16> id{};id[0]=0x42;
    const auto payload=beaconPayload(id,0x1234,0xabcd,-59);
    assert(payload.size()==25 && payload[0]==0x4c && payload[1]==0);
    assert(payload[4]==0x42 && payload[20]==0x12 && payload[21]==0x34);
    assert(payload[22]==0xab && payload[23]==0xcd && payload[24]==197);
    std::cout << "PASS: primary isolation (1000 polls), failed optional, fallback, unsupported writes, iBeacon bytes\n";
}
