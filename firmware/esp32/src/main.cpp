#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Adafruit_PN532.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <time.h>
#if __has_include("ogpass_config.h")
#include "ogpass_config.h"
#else
#define OGPASS_WIFI_SSID ""
#define OGPASS_WIFI_PASSWORD ""
#define OGPASS_API_BASE ""
#define OGPASS_READER_TOKEN ""
#define OGPASS_ROOT_CA ""
#endif

Adafruit_PN532 nfc(-1, -1);
Preferences prefs;
String pendingKey, pendingUid, heldUid, pendingPurpose="balance", serialCommand;
bool paymentArmed=false;
unsigned long paymentArmedAt=0;
unsigned long lastWifi=0,lastHeartbeat=0,lastRequest=0,lastDetected=0;
bool readerReady=false;

String uuid() {
  uint8_t b[16]; esp_fill_random(b,16);
  b[6]=(b[6]&0x0F)|0x40; b[8]=(b[8]&0x3F)|0x80;
  char out[37];
  snprintf(out,sizeof(out),"%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",b[0],b[1],b[2],b[3],b[4],b[5],b[6],b[7],b[8],b[9],b[10],b[11],b[12],b[13],b[14],b[15]);
  return String(out);
}
String uidText(uint8_t* uid,uint8_t length) {
  String result; for(uint8_t i=0;i<length;i++){if(uid[i]<16)result+="0";result+=String(uid[i],HEX);} result.toUpperCase(); return result;
}
int api(const String& path,const String& body,String& response,bool post=true) {
  if(WiFi.status()!=WL_CONNECTED) return -1;
  String base=OGPASS_API_BASE;
  if(!base.startsWith("https://") || strlen(OGPASS_ROOT_CA)<100 || time(nullptr)<1700000000) return -2;
  WiFiClientSecure client;client.setCACert(OGPASS_ROOT_CA);
  HTTPClient http;http.setTimeout(5000);http.setConnectTimeout(5000);
  if(!http.begin(client,base+path))return -3;
  http.addHeader("Content-Type","application/json");
  http.addHeader("Authorization",String("Bearer ")+OGPASS_READER_TOKEN);
  int code=post?http.POST(body):http.GET();
  if(code>0) response=http.getString();
  http.end();return code;
}
bool savePending(const String& key,const String& uid,const String& purpose){
  // Single NVS value prevents torn key/UID pairs after power failure.
  String record=key+"|"+uid+"|"+purpose;
  prefs.putString("pending",record);
  if(prefs.getString("pending","")!=record){Serial.println("ERROR NVS: operacion no enviada");return false;}
  pendingKey=key;pendingUid=uid;pendingPurpose=purpose;return true;
}
void clearPending(){
  prefs.remove("pending");
  if(!prefs.getString("pending","").isEmpty()){Serial.println("ERROR NVS: conservando referencia para evitar duplicados");return;}
  pendingKey="";pendingUid="";pendingPurpose="balance";
}
void servicePending(){
  if(pendingKey.isEmpty()||millis()-lastRequest<2500)return;
  lastRequest=millis();
  String response;
  int code=api("/api/reader/scans/"+pendingKey+"/","",response,false);
  if(code==404){
    JsonDocument data; data["uid"]=pendingUid;data["key"]=pendingKey;data["purpose"]=pendingPurpose;
    String body;serializeJson(data,body);code=api("/api/reader/scans/",body,response);
  }
  if(code!=200){Serial.printf("SIN CONFIRMACION HTTP %d; se conserva referencia para reintentar\n",code);return;}
  JsonDocument data;
  if(deserializeJson(data,response)){Serial.println("RESPUESTA INVALIDA; no aprobado");return;}
  String state=data["status"]|"unknown";
  if(state=="pairing_required"){
    Serial.printf("CODIGO PARA ASOCIAR: %s (valido 3 minutos)\n",data["pairing_code"].as<const char*>());
    Serial.println("Introduce el numero impreso y este codigo en Mi tarjeta. Luego retira y vuelve a escanear.");
    clearPending();
  }else if(state=="balance"||state=="frozen"){
    Serial.printf("TARJETA: %s\n",data["card_number"]|"sin numero impreso");
    Serial.printf("SALDO DISPONIBLE OGPASS: %lld CLP\n",data["available_balance"].as<long long>());
    Serial.println("FUENTE: ledger OGPASS actualizado. CONSULTA SIN COBRO.");
    if(state=="frozen")Serial.println("CUENTA EN REVISION: fondos no disponibles para operar");
    clearPending();
  }else if(state=="disabled"){
    Serial.println("TARJETA DESACTIVADA: consulta no disponible");clearPending();
  }else if(state=="pending"){
    Serial.printf("CONFIRMA EN TU MOVIL: %ld CLP / %s\n",data["amount"].as<long>(),pendingKey.c_str());
  }else if(state=="approved"||state=="declined"||state=="expired"||state=="reversed"){
    Serial.printf("RESULTADO: %s / %s\n",state.c_str(),pendingKey.c_str());
    if(state=="approved")Serial.println("VALIDACION REGISTRADA EN OGPASS");
    clearPending();
  }
}
void setup(){
  Serial.begin(115200);delay(500);
  Serial.println("OGPASS / ESP32 + PN532 / consulta de saldo OGPASS sin cobro");
  Serial.println("Modo normal: SALDO. Para una operacion, enviar PAGAR y acercar tarjeta en 30 segundos.");
  prefs.begin("ogpass",false);
  String saved=prefs.getString("pending","");int split=saved.indexOf('|');
  if(split>0){
    pendingKey=saved.substring(0,split);
    int modeSplit=saved.indexOf('|',split+1);
    pendingUid=modeSplit<0?saved.substring(split+1):saved.substring(split+1,modeSplit);
    // Records from the previous firmware represented payment requests.
    pendingPurpose=modeSplit<0?"payment":saved.substring(modeSplit+1);
    heldUid=pendingUid;
  }
  if(strlen(OGPASS_WIFI_SSID)==0){Serial.println("CONFIGURACION PENDIENTE: copiar src/ogpass_config.example.h a src/ogpass_config.h");}
  WiFi.mode(WIFI_STA);WiFi.begin(OGPASS_WIFI_SSID,OGPASS_WIFI_PASSWORD);
  configTime(0,0,"pool.ntp.org","time.nist.gov");
  Wire.begin(21,22);nfc.begin();
  uint32_t version=nfc.getFirmwareVersion();
  readerReady=version!=0;
  if(readerReady){nfc.SAMConfig();nfc.setPassiveActivationRetries(0x01);Serial.println("PN532 listo: ISO14443A UID. No se modifica la tarjeta.");}
  else Serial.println("PN532 NO DETECTADO: revisar I2C, alimentacion y selector del modulo");
}
void loop(){
  unsigned long now=millis();
  while(Serial.available()){
    char c=Serial.read();
    if(c=='\n'||c=='\r'){
      serialCommand.trim();serialCommand.toUpperCase();
      if(serialCommand=="PAGAR"&&pendingKey.isEmpty()){paymentArmed=true;paymentArmedAt=now;Serial.println("PROXIMA LECTURA: PAGO, requiere confirmacion movil. Caduca en 30 s.");}
      else if(serialCommand=="SALDO"){paymentArmed=false;Serial.println("PROXIMA LECTURA: CONSULTA SIN COBRO");}
      serialCommand="";
    }else if(serialCommand.length()<16){serialCommand+=c;}
  }
  if(paymentArmed&&now-paymentArmedAt>30000){paymentArmed=false;Serial.println("MODO PAGO EXPIRADO: vuelta a consulta de saldo");}
  if(WiFi.status()!=WL_CONNECTED&&now-lastWifi>10000){lastWifi=now;WiFi.reconnect();}
  if(readerReady&&now-lastHeartbeat>15000){lastHeartbeat=now;String response;int code=api("/api/reader/heartbeat/","{}",response);if(code!=200)Serial.printf("Lector sin conexion verificada: %d\n",code);}
  servicePending();
  if(!readerReady){delay(100);return;}
  uint8_t uid[10],len=0;
  bool detected=nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A,uid,&len,100);
  if(!detected){if(millis()-lastDetected>1500 && pendingKey.isEmpty())heldUid="";return;}
  lastDetected=millis();
  if(len!=4&&len!=7&&len!=10)return;
  String current=uidText(uid,len);
  if(current==heldUid||!pendingKey.isEmpty())return;
  heldUid=current;
  Serial.println("TAG UID: "+current);
  if(WiFi.status()!=WL_CONNECTED){Serial.println("SIN CONEXION: retira el tag y vuelve a tocar cuando haya red");return;}
  String purpose=paymentArmed?"payment":"balance";
  if(!savePending(uuid(),current,purpose))return;
  paymentArmed=false;
  Serial.println(purpose=="balance"?"Consultando fondos OGPASS. No se realizara un cobro.":"Solicitando operacion. Confirma en tu movil.");
}
