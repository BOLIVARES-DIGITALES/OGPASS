#pragma once
// Compile coverage only. No real credentials, no valid CA, reserved .invalid host.
// Never flash this fixture onto a device for integration testing.
#define OGPASS_WIFI_SSID "OGPASS-COMPILE-ONLY"
#define OGPASS_WIFI_PASSWORD "compile-only-not-a-real-password"
#define OGPASS_API_BASE "https://ogpass-compile.invalid"
#define OGPASS_READER_TOKEN "compile-only-not-a-real-reader-token-000000"
static const char OGPASS_ROOT_CA[] =
    "-----BEGIN CERTIFICATE-----\n"
    "Compile-only-invalid-certificate-no-TLS-session-can-validate-with-this-fixture-"
    "00000000000000000000000000000000000000000000000000000000000000000000000000\n"
    "-----END CERTIFICATE-----\n";
