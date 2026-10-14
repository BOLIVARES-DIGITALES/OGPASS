#pragma once
#include <Arduino.h>
#include <SPI.h>
#include <MFRC522.h>
#include <atomic>
#include "../../core/OgpassReader.h"

namespace ogpass {
class Rc522Reader final : public OgpassReader {
    MFRC522 chip{5,27};
    std::atomic<Health> state{Health::OFFLINE};
    uint16_t atqa=0;
public:
    const char* name() const override {return "rc522";}
    bool begin() override {
        SPI.begin(18,19,23,5);
        chip.PCD_Init();
        probe();
        return state==Health::CONNECTED;
    }
    void probe() {
        const byte version=chip.PCD_ReadRegister(MFRC522::VersionReg);
        state=(version==0 || version==0xff) ? Health::ERROR : Health::CONNECTED;
    }
    Health health() const override {return state.load();}
    uint16_t capabilities() const override {return IDENTIFY|READ|HEALTH;}
    bool detect() override {
        byte answer[2]={0,0};byte length=2;
        const auto status=chip.PICC_RequestA(answer,&length);
        atqa=static_cast<uint16_t>(answer[0]) | (static_cast<uint16_t>(answer[1])<<8);
        return status==MFRC522::STATUS_OK || status==MFRC522::STATUS_COLLISION;
    }
    Result read(Detection& out) override {
        const uint32_t start=millis();
        if(!chip.PICC_ReadCardSerial()) return Result::NO_SIGNAL;
        out=Detection{};
        snprintf(out.reader,sizeof(out.reader),"rc522");
        snprintf(out.technology,sizeof(out.technology),"NFC");
        snprintf(out.protocol,sizeof(out.protocol),"ISO14443A");
        for(byte i=0;i<chip.uid.size && i<10;i++) snprintf(out.uid+2*i,3,"%02X",chip.uid.uidByte[i]);
        out.sak=chip.uid.sak;out.atqa=atqa;
        snprintf(out.type,sizeof(out.type),"%s",chip.PICC_GetTypeName(chip.PICC_GetType(chip.uid.sak)));
        chip.PICC_HaltA();chip.PCD_StopCrypto1();
        out.latencyMs=millis()-start;
        return Result::OK;
    }
};
}
