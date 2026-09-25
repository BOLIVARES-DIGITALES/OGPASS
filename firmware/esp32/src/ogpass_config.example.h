#pragma once
#define OGPASS_WIFI_SSID "TU_WIFI"
#define OGPASS_WIFI_PASSWORD "TU_PASSWORD"
#define OGPASS_API_BASE "https://tu-dominio.cl"
#define OGPASS_READER_TOKEN "TOKEN_GENERADO_POR_PROVISION_READER"
// Copia el certificado PEM de la CA raíz que valida el certificado del dominio.
// No uses setInsecure. En producción HTTP no está permitido.
#define OGPASS_ROOT_CA R"PEM(-----BEGIN CERTIFICATE-----
REEMPLAZAR_POR_CA_RAIZ
-----END CERTIFICATE-----
)PEM"
inventario de dependencias → congelar Smartbar → identificar legacy realmente desconectado → elegir arquitectura CSS → establecer nuevos entrypoints JS → migrar únicamente frontend público → build optimizado de producción.inventario de dependencias → congelar Smartbar → identificar legacy realmente desconectado → elegir arquitectura CSS → establecer nuevos entrypoints JS → migrar únicamente frontend público → build optimizado de producción.