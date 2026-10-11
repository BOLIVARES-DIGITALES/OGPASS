#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_PN532.h>

// =============================================================================
// OGPASS - PN532 HARDWARE VALIDATION
//
// ESP32 + PN532 / I2C / 4 cables
//
// PN532 VCC -> ESP32 3V3
// PN532 GND -> ESP32 GND
// PN532 SDA -> GPIO21
// PN532 SCL -> GPIO22
//
// IRQ / RSTO no conectados fisicamente.
//
// COMANDOS:
//   TEST    -> inicializacion completa
//   I2C     -> prueba simple
//   BENCH   -> benchmark 25 / 50 / 100 kHz
//   SCAN    -> una lectura NFC, hasta 5 segundos
//   STATUS  -> estado
//
// SOLO LECTURA.
// =============================================================================


// -----------------------------------------------------------------------------
// Hardware
// -----------------------------------------------------------------------------

constexpr uint8_t PN532_IRQ_PIN   = 27;
constexpr uint8_t PN532_RESET_PIN = 26;

constexpr uint8_t PN532_SDA_PIN = 21;
constexpr uint8_t PN532_SCL_PIN = 22;

constexpr uint8_t PN532_ADDRESS = 0x24;


// -----------------------------------------------------------------------------
// Tolerant configuration
// -----------------------------------------------------------------------------

constexpr uint32_t DEFAULT_I2C_FREQUENCY = 50000;

constexpr uint16_t I2C_TIMEOUT_MS = 3000;

constexpr uint16_t NFC_SCAN_TIMEOUT_MS = 5000;

constexpr uint8_t INITIAL_PROBE_COUNT = 5;

constexpr uint8_t INITIAL_REQUIRED_OK = 4;


// -----------------------------------------------------------------------------
// PN532
// -----------------------------------------------------------------------------

Adafruit_PN532 nfc(
    PN532_IRQ_PIN,
    PN532_RESET_PIN,
    &Wire
);


// -----------------------------------------------------------------------------
// State
// -----------------------------------------------------------------------------

bool readerReady = false;

uint32_t activeFrequency =
    DEFAULT_I2C_FREQUENCY;

String serialCommand;


// =============================================================================
// I2C
// =============================================================================

uint8_t probePn532() {

    Wire.beginTransmission(
        PN532_ADDRESS
    );

    return Wire.endTransmission();
}


bool probePn532Verbose() {

    Serial.println(
        "I2C_PROBE"
    );

    uint8_t error =
        probePn532();

    if (error == 0) {

        Serial.printf(
            "PN532_I2C_OK address=0x%02X freq=%lu\n",
            PN532_ADDRESS,
            activeFrequency
        );

        return true;
    }

    Serial.printf(
        "PN532_I2C_FAILED address=0x%02X error=%u freq=%lu\n",
        PN532_ADDRESS,
        error,
        activeFrequency
    );

    return false;
}


// =============================================================================
// STABILITY TEST
// =============================================================================

bool stabilityCheck(
    uint8_t attempts,
    uint8_t required
) {

    uint8_t success = 0;

    Serial.printf(
        "I2C_STABILITY_BEGIN attempts=%u required=%u\n",
        attempts,
        required
    );

    for (
        uint8_t i = 0;
        i < attempts;
        i++
    ) {

        uint8_t error =
            probePn532();

        if (error == 0) {

            success++;

            Serial.printf(
                "PROBE %u/%u OK\n",
                i + 1,
                attempts
            );

        } else {

            Serial.printf(
                "PROBE %u/%u FAIL error=%u\n",
                i + 1,
                attempts,
                error
            );
        }

        delay(250);
    }

    Serial.printf(
        "I2C_STABILITY_RESULT %u/%u\n",
        success,
        attempts
    );

    return success >= required;
}


// =============================================================================
// BENCHMARK
// =============================================================================

void benchmarkFrequency(
    uint32_t frequency
) {

    Wire.setClock(
        frequency
    );

    activeFrequency =
        frequency;

    delay(100);

    Serial.println();
    Serial.printf(
        "BENCH_FREQ_BEGIN %lu Hz\n",
        frequency
    );

    constexpr uint8_t attempts = 10;

    uint8_t success = 0;

    for (
        uint8_t i = 0;
        i < attempts;
        i++
    ) {

        uint8_t error =
            probePn532();

        if (error == 0) {

            success++;

            Serial.printf(
                "%02u OK\n",
                i + 1
            );

        } else {

            Serial.printf(
                "%02u FAIL error=%u\n",
                i + 1,
                error
            );
        }

        delay(200);
    }

    Serial.printf(
        "BENCH_FREQ_RESULT freq=%lu success=%u/%u\n",
        frequency,
        success,
        attempts
    );
}


void runBenchmark() {

    Serial.println();
    Serial.println(
        "================================"
    );

    Serial.println(
        "OGPASS_I2C_HARDWARE_BENCH"
    );

    Serial.println(
        "================================"
    );

    benchmarkFrequency(
        25000
    );

    benchmarkFrequency(
        50000
    );

    benchmarkFrequency(
        100000
    );

    // Return to tolerant default.
    Wire.setClock(
        DEFAULT_I2C_FREQUENCY
    );

    activeFrequency =
        DEFAULT_I2C_FREQUENCY;

    Serial.println();
    Serial.println(
        "BENCH_COMPLETE"
    );

    Serial.println(
        "DEFAULT_RESTORED=50000Hz"
    );
}


// =============================================================================
// UID
// =============================================================================

void printUid(
    const uint8_t *uid,
    uint8_t uidLength
) {

    Serial.println();
    Serial.println(
        "--------------------------------"
    );

    Serial.println(
        "TAG_DETECTED"
    );

    Serial.printf(
        "UID_LENGTH=%u\n",
        uidLength
    );

    Serial.print(
        "UID="
    );

    for (
        uint8_t i = 0;
        i < uidLength;
        i++
    ) {

        if (
            uid[i] < 0x10
        ) {
            Serial.print("0");
        }

        Serial.print(
            uid[i],
            HEX
        );

        if (
            i + 1 < uidLength
        ) {
            Serial.print(":");
        }
    }

    Serial.println();

    Serial.println(
        "PROTOCOL=ISO14443A"
    );

    Serial.println(
        "MODE=READ_ONLY"
    );

    Serial.println(
        "--------------------------------"
    );
}


// =============================================================================
// INITIALIZATION
// =============================================================================

bool initializeReader() {

    readerReady = false;

    Serial.println();
    Serial.println(
        "================================"
    );

    Serial.println(
        "OGPASS_PN532_TOLERANT_TEST"
    );

    Serial.println(
        "================================"
    );


    // -------------------------------------------------------------------------
    // I2C
    // -------------------------------------------------------------------------

    Wire.end();

    delay(250);

    Wire.begin(
        PN532_SDA_PIN,
        PN532_SCL_PIN,
        DEFAULT_I2C_FREQUENCY
    );

    activeFrequency =
        DEFAULT_I2C_FREQUENCY;

    Wire.setTimeOut(
        I2C_TIMEOUT_MS
    );

    delay(500);

    Serial.printf(
        "I2C_INITIALIZED SDA=21 SCL=22 FREQ=%lu TIMEOUT=%u\n",
        activeFrequency,
        I2C_TIMEOUT_MS
    );


    // -------------------------------------------------------------------------
    // Stability
    // -------------------------------------------------------------------------

    if (
        !stabilityCheck(
            INITIAL_PROBE_COUNT,
            INITIAL_REQUIRED_OK
        )
    ) {

        Serial.println(
            "TEST_STOPPED_I2C_UNSTABLE"
        );

        return false;
    }


    // -------------------------------------------------------------------------
    // PN532
    // -------------------------------------------------------------------------

    Serial.println(
        "PN532_BEGIN"
    );

    nfc.begin();

    delay(500);


    // -------------------------------------------------------------------------
    // Firmware
    // -------------------------------------------------------------------------

    Serial.println(
        "PN532_FIRMWARE_QUERY"
    );

    uint32_t version =
        nfc.getFirmwareVersion();

    if (!version) {

        Serial.println(
            "PN532_FIRMWARE_QUERY_FAILED"
        );

        return false;
    }

    uint8_t chip =
        (version >> 24) & 0xFF;

    uint8_t major =
        (version >> 16) & 0xFF;

    uint8_t minor =
        (version >> 8) & 0xFF;

    uint8_t support =
        version & 0xFF;

    Serial.printf(
        "PN532_FIRMWARE_OK chip=0x%02X firmware=%u.%u support=0x%02X\n",
        chip,
        major,
        minor,
        support
    );

    delay(500);


    // -------------------------------------------------------------------------
    // SAM
    // -------------------------------------------------------------------------

    Serial.println(
        "PN532_SAMCONFIG"
    );

    if (
        !nfc.SAMConfig()
    ) {

        Serial.println(
            "PN532_SAMCONFIG_FAILED"
        );

        return false;
    }

    Serial.println(
        "PN532_SAMCONFIG_OK"
    );


    // -------------------------------------------------------------------------
    // Passive activation retries
    // -------------------------------------------------------------------------

    if (
        !nfc.setPassiveActivationRetries(
            0x05
        )
    ) {

        Serial.println(
            "PN532_RETRY_CONFIG_FAILED"
        );

        return false;
    }

    Serial.println(
        "PN532_RETRY_CONFIG_OK retries=5"
    );


    readerReady = true;

    Serial.println();
    Serial.println(
        "OGPASS_PN532_READY"
    );

    Serial.println(
        "I2C_MODE=TOLERANT"
    );

    Serial.println(
        "I2C_FREQ=50000"
    );

    Serial.println(
        "I2C_TIMEOUT=3000ms"
    );

    Serial.println(
        "NFC_TIMEOUT=5000ms"
    );

    Serial.println();

    Serial.println(
        "ACERCA TARJETA Y ESCRIBE SCAN"
    );

    return true;
}


// =============================================================================
// NFC SINGLE SCAN
// =============================================================================

void scanCard() {

    Serial.println();
    Serial.println(
        "================================"
    );

    Serial.println(
        "OGPASS_NFC_SCAN"
    );

    Serial.println(
        "================================"
    );

    if (
        !readerReady
    ) {

        Serial.println(
            "SCAN_ABORTED reader_not_ready"
        );

        return;
    }


    // -------------------------------------------------------------------------
    // Verify bus immediately before NFC transaction
    // -------------------------------------------------------------------------

    if (
        !stabilityCheck(
            3,
            2
        )
    ) {

        readerReady = false;

        Serial.println(
            "SCAN_ABORTED i2c_unstable"
        );

        return;
    }


    Serial.println(
        "SCAN_STARTED"
    );

    Serial.println(
        "MANTEN_TARJETA_SOBRE_ANTENA"
    );


    uint8_t uid[10] = {0};

    uint8_t uidLength = 0;


    unsigned long start =
        millis();


    bool detected =
        nfc.readPassiveTargetID(
            PN532_MIFARE_ISO14443A,
            uid,
            &uidLength,
            NFC_SCAN_TIMEOUT_MS
        );


    unsigned long duration =
        millis() - start;


    Serial.printf(
        "SCAN_DURATION=%lu ms\n",
        duration
    );


    if (
        !detected
    ) {

        Serial.println(
            "NO_TAG_DETECTED"
        );

        Serial.println(
            "SCAN_FINISHED"
        );

        return;
    }


    if (
        uidLength == 0 ||
        uidLength > sizeof(uid)
    ) {

        Serial.printf(
            "UID_LENGTH_INVALID=%u\n",
            uidLength
        );

        return;
    }


    printUid(
        uid,
        uidLength
    );


    Serial.println(
        "SCAN_FINISHED"
    );
}


// =============================================================================
// STATUS
// =============================================================================

void printStatus() {

    Serial.println();

    Serial.println(
        "OGPASS_STATUS"
    );

    Serial.printf(
        "reader_ready=%s\n",
        readerReady
            ? "true"
            : "false"
    );

    Serial.printf(
        "i2c_frequency=%lu\n",
        activeFrequency
    );

    Serial.printf(
        "i2c_timeout=%u\n",
        I2C_TIMEOUT_MS
    );

    Serial.printf(
        "nfc_timeout=%u\n",
        NFC_SCAN_TIMEOUT_MS
    );

    Serial.println(
        "interface=I2C"
    );

    Serial.println(
        "wiring=4-wire"
    );

    Serial.println(
        "irq_connected=false"
    );

    Serial.println();
}


// =============================================================================
// SERIAL
// =============================================================================

void processSerial() {

    while (
        Serial.available()
    ) {

        char c =
            Serial.read();


        if (
            c == '\n' ||
            c == '\r'
        ) {

            serialCommand.trim();

            serialCommand.toUpperCase();


            if (
                serialCommand.length() == 0
            ) {
                continue;
            }


            if (
                serialCommand == "TEST"
            ) {

                initializeReader();

            } else if (
                serialCommand == "I2C"
            ) {

                probePn532Verbose();

            } else if (
                serialCommand == "BENCH"
            ) {

                runBenchmark();

            } else if (
                serialCommand == "SCAN"
            ) {

                scanCard();

            } else if (
                serialCommand == "STATUS"
            ) {

                printStatus();

            } else {

                Serial.println(
                    "COMANDO_DESCONOCIDO"
                );

                Serial.println(
                    "COMANDOS: TEST | I2C | BENCH | SCAN | STATUS"
                );
            }


            serialCommand = "";

        } else {

            if (
                serialCommand.length() < 32
            ) {

                serialCommand += c;
            }
        }
    }
}


// =============================================================================
// SETUP
// =============================================================================

void setup() {

    Serial.begin(
        115200
    );

    delay(
        1500
    );

    initializeReader();

    Serial.println();
    Serial.println(
        "COMANDOS: TEST | I2C | BENCH | SCAN | STATUS"
    );
}


// =============================================================================
// LOOP
// =============================================================================

void loop() {

    processSerial();

    delay(
        10
    );
}