#include <Arduino.h>
#include <Wire.h>

void scanBus(){
  uint8_t found=0;
  Serial.println("OGPASS_I2C_SCAN_BEGIN");
  for(uint8_t address=1;address<127;address++){
    Wire.beginTransmission(address);
    uint8_t error=Wire.endTransmission();
    if(error==0){
      Serial.printf("OGPASS_I2C_DEVICE 0x%02X\n",address);
      found++;
    }
  }
  Serial.printf("OGPASS_I2C_SCAN_END devices=%u pn532_0x24=%s\n",found,found?"check_address_above":"not_detected");
}

void setup(){
  Serial.begin(115200);
  delay(500);
  Wire.begin(21,22);
  scanBus();
}

void loop(){
  if(Serial.available()){
    while(Serial.available())Serial.read();
    scanBus();
  }
  delay(100);
}
