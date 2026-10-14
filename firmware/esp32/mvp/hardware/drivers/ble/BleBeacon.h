#pragma once
#include <atomic>
#include <BLEDevice.h>
#include <BLEAdvertising.h>
#include "BeaconPayload.h"
#include "../../core/OgpassReader.h"

namespace ogpass {
class BleBeacon final : public OgpassReader {
    std::atomic<Health> state{Health::Disabled};
public:
    const char* name() const override {return "ble";}
    bool begin() override {
        // Lab UUID identifies this prototype, never a person or wallet.
        const std::array<uint8_t,16> uuid{{0x08,0x50,0xa5,0x50,0x77,0x21,0x4e,0xa0,0x9f,0x0f,0x22,0x10,0x00,0x00,0x00,0x01}};
        BLEDevice::init("OGPASS-LAB");
        BLEAdvertisementData advertisement;
        advertisement.setFlags(0x06);
        auto bytes=beaconPayload(uuid,1,1,-59);
        advertisement.setManufacturerData(std::string(reinterpret_cast<const char*>(bytes.data()),bytes.size()));
        BLEAdvertising* advertising=BLEDevice::getAdvertising();
        advertising->setAdvertisementData(advertisement);
        advertising->setScanResponse(false);
        advertising->setAdvertisementType(ADV_TYPE_NONCONN_IND);
        advertising->start();
        state=Health::CONNECTED; // Stack started; RF reception remains a bench test.
        return true;
    }
    Health health() const override {return state.load();}
    bool detect() override {return false;}
    Result read(Detection&) override {return Result::UNSUPPORTED;}
    uint16_t capabilities() const override {return BEACON|HEALTH;}
};
}
