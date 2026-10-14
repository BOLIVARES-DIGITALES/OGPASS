# Contrato v1

El portal NFC/QR añade `GET /api/v1/tags/<code>/`: respuesta pública limitada o
vista del titular según la sesión Django. Conocer `code` no concede propiedad.
Ver [contrato, activación y bloqueo](TAG_PORTAL.md).

Se conservan todas las rutas previas. Respuestas privadas usan `Cache-Control:
no-store, private`. La sesión Django y CSRF siguen siendo necesarios para acciones
del usuario/staff. Únicamente scans y heartbeat usan Bearer de lector y están
exentos de CSRF; el token siempre se valida en el servidor.

| Ruta `/api/v1/` | Método | Acceso / función |
|---|---|---|
| me/ | GET | Sesión; IDs públicos de la propia cuenta, nunca PRIVATE_ID |
| wallet/ | GET | Sesión; wallet propia, CLP y saldo disponible |
| devices/, readers/ | GET | Sesión; propios/relacionados; staff ve todos |
| devices/register/ | POST | Staff + CSRF; nombre, driver; token una sola vez |
| devices/heartbeat/ | POST | Bearer; versión de firmware y health por driver |
| devices/{id}/disable/ | POST | Staff + CSRF; deshabilita lector |
| credentials/ | GET | Sesión; únicamente credenciales propias |
| credentials/scan/ | POST | Bearer; evento idempotente, consulta sin cobro |
| credentials/assign/ | POST | Staff + CSRF; request_id, scan_key, number |
| events/ | GET/SSE | Sesión; avisos de la propia wallet |
| events/staff/ | GET/SSE | Staff; avisos administrativos |
| events/recent/ | GET | Sesión; eventos propios; staff ve todos |
| health/ | GET | Salud de DB/API, sin credenciales |

Ejemplo de cuerpo de scan (IDs de ejemplo, no ejecuta una lectura física):

```json
{"event_id":"503d2aa8-f4fc-48c1-ac5b-a9dc8994b59d","reader":"rc522",
 "technology":"NFC","protocol":"ISO14443A","uid":"04A1B2C3D4E5F6",
 "purpose":"balance","metadata":{"sak":8,"atqa":4,"latency_ms":12}}
```

`device_id` se deriva de la autenticación; si se envía uno diferente, se rechaza.
`request_id` es correlación y puede cambiar al reintentar; `event_id` y contenido
semántico deben conservarse. `timestamp` opcional representa observación del
dispositivo; el servidor conserva siempre su propia fecha de recepción.
201 significa registrado y 200 reintento reconocido, nunca pago aprobado.
409 indica colisión de referencia. Un protocolo no implementado devuelve
UNKNOWN_TECHNOLOGY sin crear tag, wallet ni saldo.

En modo product no se exponen UID, protocolo, metadatos ni capacidades a usuarios.
Modo developer exige además staff. La asociación conserva la verificación del
número impreso, titular, lectura reciente y lector disponible; no se admite
asignar un UID arbitrario mediante la API nueva.
