#include <Arduino.h>
#include <ArduinoJson.h>
#include <SPI.h>
#include <Wire.h>
#include <MFRC522.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <atomic>
#if defined(OGPASS_COMPILE_NETWORK_FIXTURE)
#include "../mvp/hardware/tests/network_fixture.h"
#elif __has_include("ogpass_config.h")
#include "ogpass_config.h"
#endif
#if !defined(OGPASS_WIFI_SSID) || !defined(OGPASS_WIFI_PASSWORD) || !defined(OGPASS_API_BASE) || !defined(OGPASS_READER_TOKEN)
#undef OGPASS_WIFI_SSID
#undef OGPASS_WIFI_PASSWORD
#undef OGPASS_API_BASE
#undef OGPASS_READER_TOKEN
#define OGPASS_WIFI_SSID ""
#define OGPASS_WIFI_PASSWORD ""
#define OGPASS_API_BASE ""
#define OGPASS_READER_TOKEN ""
#define OGPASS_ROOT_CA ""
#endif
#ifndef OGPASS_DEVELOPER_MODE
#define OGPASS_DEVELOPER_MODE 0
#endif
#ifndef OGPASS_ENABLE_PN532
#define OGPASS_ENABLE_PN532 1
#endif
#ifndef OGPASS_ENABLE_BLE
#define OGPASS_ENABLE_BLE 0
#endif
#include "../mvp/hardware/core/ReaderManager.h"
#include "../mvp/hardware/core/HttpsEvents.h"
#include "../mvp/hardware/drivers/rc522/Rc522Reader.h"
#include "../mvp/hardware/drivers/pn532/Pn532Diagnostic.h"
#if OGPASS_ENABLE_BLE
#include <BLEDevice.h>
#include <BLEAdvertising.h>
#include "../mvp/hardware/drivers/ble/BleBeacon.h"
#endif

using namespace ogpass;
Rc522Reader primary;
Pn532Diagnostic optional(OGPASS_ENABLE_PN532);
#if OGPASS_ENABLE_BLE
BleBeacon beacon;
#endif
ReaderManager readers;
HttpsEvents transport;
TaskHandle_t optionalTaskHandle=nullptr;
std::atomic<bool> optionalStarted{false};
QueueHandle_t optionalEvents=nullptr;
String command;

Health bleHealth() {
#if OGPASS_ENABLE_BLE
    return beacon.health();
#else
    return Health::Disabled;
#endif
}

void optionalTask(void*) {
    readers.beginOptional();optionalStarted=true;
    for(;;) {
        Detection event;
        if(readers.pollOptional(event)) xQueueSend(optionalEvents,&event,0);
        // Explicit re-probe stays on this task, never the primary loop.
        if(ulTaskNotifyTake(pdTRUE,pdMS_TO_TICKS(100))>0) optional.reset();
    }
}

void networkTask(void*) {
    transport.beginNetwork();
    for(;;) {
        transport.tick(primary.health(),optional.health(),bleHealth());
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}

void status() {
    JsonDocument value;
    value["device"]="OGPASS-ESP32";value["protocol"]=2;
    value["firmware_version"]="ogpass-core-0.1";
    value["reader_ready"]=primary.health()==Health::CONNECTED;
    value["wifi_connected"]=WiFi.status()==WL_CONNECTED;
    value["backend_online"]=transport.online && millis()-transport.heartbeatAt.load()<45000;
    value["heartbeat_code"]=transport.heartbeatCode.load();
    value["configured"]=transport.configured();
    value["readers"]["rc522"]=healthName(primary.health());
    value["readers"]["pn532"]=healthName(optional.health());
    value["readers"]["ble"]=healthName(bleHealth());
    value["optional_started"]=optionalStarted.load();
    value["mode"]=OGPASS_DEVELOPER_MODE?"developer":"product";
    Serial.print("OGPASS_STATUS ");serializeJson(value,Serial);Serial.println();
}

void eventId(char* result) {
    uint8_t b[16];esp_fill_random(b,16);b[6]=(b[6]&15)|64;b[8]=(b[8]&63)|128;
    snprintf(result,37,"%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",b[0],b[1],b[2],b[3],b[4],b[5],b[6],b[7],b[8],b[9],b[10],b[11],b[12],b[13],b[14],b[15]);
}

void setup() {
    Serial.begin(115200);
    readers.add(primary,Role::PRIMARY);readers.add(optional,Role::OPTIONAL);
#if OGPASS_ENABLE_BLE
    readers.add(beacon,Role::RADIO);
#endif
    // RC522 always starts first. Neither optional task is awaited.
    readers.beginPrimary();
    transport.beginQueue();optionalEvents=xQueueCreate(4,sizeof(Detection));
    if(optionalEvents) {
        if(xTaskCreatePinnedToCore(optionalTask,"ogpass-optional",8192,nullptr,1,&optionalTaskHandle,0)!=pdPASS)
            Serial.println("OGPASS_OPTIONAL_TASK_ERROR primary_continues");
    }
    if(xTaskCreatePinnedToCore(networkTask,"ogpass-network",12288,nullptr,1,nullptr,0)!=pdPASS)
        Serial.println("OGPASS_NETWORK_TASK_ERROR local_detection_only");
    Serial.println("OGPASS: RC522 PRIMARY | PN532 OPTIONAL | consulta sin cobro");
    Serial.println("Comandos: STATUS, I2CSCAN, SALDO. Escritura y pagos deshabilitados.");
    status();
}

void loop() {
    static uint32_t lastProbe=0;
    if(millis()-lastProbe>=2000) {lastProbe=millis();primary.probe();}
    while(Serial.available()) {
        const char c=Serial.read();
        if(c=='\n' || c=='\r') {
            command.trim();command.toUpperCase();
            if(command=="STATUS") status();
            else if(command=="I2CSCAN" && optionalTaskHandle) {
                xTaskNotifyGive(optionalTaskHandle);
                Serial.println("OGPASS_I2C_SCAN_QUEUED consultar STATUS; ACK no certifica lectura PN532");
            } else if(command=="SALDO") Serial.println("CONSULTA SIN COBRO");
            else if(command=="PAGAR") Serial.println("PAGOS DESHABILITADOS en este firmware de lanzamiento");
            command="";
        } else if(command.length()<20) command+=c;
    }
    Detection detection;
    // Only consume an already available optional result; never call optional I/O.
    const bool detected=readers.pollPrimary(detection) ||
        (optionalEvents && xQueueReceive(optionalEvents,&detection,0)==pdTRUE);
    if(detected) {
        QueuedDetection event;event.value=detection;eventId(event.eventId);
        JsonDocument value;value["event_id"]=event.eventId;value["state"]="detected";
        value["reader"]=detection.reader;value["technology"]=detection.technology;
#if OGPASS_DEVELOPER_MODE
        value["uid"]=detection.uid;value["protocol"]=detection.protocol;
        value["sak"]=detection.sak;value["atqa"]=detection.atqa;
        value["type"]=detection.type;value["latency_ms"]=detection.latencyMs;
#endif
        Serial.print("OGPASS_NFC_EVENT ");serializeJson(value,Serial);Serial.println();
        if(transport.configured() && !transport.enqueue(event)) Serial.println("OGPASS_QUEUE_FULL event_not_sent");
    }
    delay(5);
}
