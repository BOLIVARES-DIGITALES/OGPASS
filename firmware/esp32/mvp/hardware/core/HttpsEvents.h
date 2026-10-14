#pragma once
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <atomic>
#include <time.h>
#include "OgpassReader.h"

namespace ogpass {
struct QueuedDetection { Detection value; char eventId[37]{}; };
class HttpsEvents {
    QueueHandle_t queue=nullptr;
    Preferences storage;
    String pending;
    uint32_t lastHeartbeat=0,lastAttempt=0,lastWifi=0;
public:
    std::atomic<bool> online{false};
    std::atomic<int> heartbeatCode{0};
    std::atomic<uint32_t> heartbeatAt{0};
    bool configured() const {
        return strlen(OGPASS_WIFI_SSID)>0 && strlen(OGPASS_READER_TOKEN)>=32 &&
               String(OGPASS_API_BASE).startsWith("https://") && strlen(OGPASS_ROOT_CA)>100;
    }
    void beginQueue() {queue=xQueueCreate(8,sizeof(QueuedDetection));}
    bool enqueue(const QueuedDetection& event) {return queue && xQueueSend(queue,&event,0)==pdTRUE;}
    void beginNetwork() {
        storage.begin("ogpass-events",false);
        pending=storage.getString("pending","");
        if(configured()) {
            WiFi.mode(WIFI_STA);WiFi.begin(OGPASS_WIFI_SSID,OGPASS_WIFI_PASSWORD);
            configTime(0,0,"pool.ntp.org","time.nist.gov");
        }
    }
    int post(const char* path, const String& body, String& response) {
        if(!configured() || WiFi.status()!=WL_CONNECTED || time(nullptr)<1700000000) return -2;
        WiFiClientSecure client;client.setCACert(OGPASS_ROOT_CA);
        HTTPClient http;http.setTimeout(3000);http.setConnectTimeout(3000);
        if(!http.begin(client,String(OGPASS_API_BASE)+path)) return -3;
        http.addHeader("Authorization",String("Bearer ")+OGPASS_READER_TOKEN);
        http.addHeader("Content-Type","application/json");
        const int status=http.POST(body);
        if(status>0) response=http.getString();
        http.end();return status;
    }
    void tick(Health primary,Health optional,Health ble) {
        const uint32_t now=millis();
        if(!configured()) return;
        if(WiFi.status()!=WL_CONNECTED) {
            online=false;
            if(now-lastWifi>10000) {lastWifi=now;WiFi.reconnect();}
            return;
        }
        if(now-lastHeartbeat>=15000) {
            lastHeartbeat=now;
            JsonDocument packet;packet["firmware_version"]="ogpass-core-0.1";
            packet["health"]["rc522"]=healthName(primary);
            packet["health"]["pn532"]=healthName(optional);
            packet["health"]["ble"]=healthName(ble);
            String body,response;serializeJson(packet,body);
            const int code=post("/api/v1/devices/heartbeat/",body,response);
            JsonDocument reply;
            const bool valid=code==200 && !deserializeJson(reply,response) && reply["device_id"].is<const char*>();
            heartbeatCode=code;online=valid;
            if(valid) heartbeatAt=now;
            else Serial.printf("OGPASS_NETWORK heartbeat_http=%d\n",code);
        }
        if(pending.isEmpty() && queue) {
            QueuedDetection event;
            if(xQueueReceive(queue,&event,0)==pdTRUE) {
                JsonDocument packet;
                packet["event_id"]=event.eventId;packet["request_id"]=event.eventId;
                packet["reader"]=event.value.reader;packet["technology"]=event.value.technology;
                packet["protocol"]=event.value.protocol;packet["uid"]=event.value.uid;
                packet["purpose"]="balance";
                packet["metadata"]["sak"]=event.value.sak;
                packet["metadata"]["atqa"]=event.value.atqa;
                packet["metadata"]["type"]=event.value.type;
                packet["metadata"]["latency_ms"]=event.value.latencyMs;
                serializeJson(packet,pending);
                storage.putString("pending",pending);
                if(storage.getString("pending","")!=pending) {
                    Serial.println("OGPASS_STORAGE_ERROR event_not_sent");
                    pending="";return;
                }
            }
        }
        if(pending.isEmpty() || now-lastAttempt<3000) return;
        lastAttempt=now;
        String response;const int code=post("/api/v1/credentials/scan/",pending,response);
        JsonDocument request,reply;
        if(deserializeJson(request,pending)) {Serial.println("OGPASS_STORAGE_ERROR pending_requires_review");return;}
        const bool acknowledged=(code==200 || code==201) && !deserializeJson(reply,response) &&
            String(reply["event_id"]|"")==String(request["event_id"]|"") &&
            (String(reply["status"]|"")=="detected" || String(reply["status"]|"")=="UNKNOWN_TECHNOLOGY");
        if(!acknowledged) {Serial.printf("OGPASS_DELIVERY_PENDING http=%d\n",code);return;}
        Serial.printf("OGPASS_SCAN_RESULT event_id=%s status=%s CONSULTA_SIN_COBRO\n",
                      request["event_id"].as<const char*>(),reply["scan"]["status"]|"unknown");
        if(reply["scan"]["available_balance"].is<int64_t>())
            Serial.printf("SALDO OGPASS: %lld CLP\n",reply["scan"]["available_balance"].as<int64_t>());
        storage.remove("pending");
        if(storage.getString("pending","").isEmpty()) pending="";
    }
};
}
