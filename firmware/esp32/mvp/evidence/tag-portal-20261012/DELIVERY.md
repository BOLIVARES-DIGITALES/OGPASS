# Entrega: portal NFC/QR multiusuario

Fecha: 12 de octubre de 2026. Basado en el flujo WOOD descrito por el usuario;
su aplicación externa no fue auditada. Código implementado en el único MVP Django.

## Resultado

- `/w/<code>/`: vistas nueva, visitante, titular y acceso no disponible.
- `/api/v1/tags/<code>/`: misma lista de campos permitidos, según sesión.
- `/my/tags/`: enlace NFC/QR para cada tarjeta ya asociada y bloqueo por pérdida.
- Administración: inventario sin titular, asignación de tarjeta ya verificada,
  edición de mensajes públicos y tema, sin regrabar URL.
- Sesión HttpOnly existente; sin tokens locales de dueño ni recuperación por
  correo + cuatro dígitos. El código público no concede derechos.
- Activación y bloqueo idempotentes, auditoría y eventos; bloqueo aplicado al Tag,
  credencial normalizada y portal. Ledger y fondos se conservan.
- CSP en el portal, no-store, política de referencias al mismo origen, CSRF y
  rate limiting agrupado para evitar evasión al cambiar código.
- Retorno seguro al portal después de login/registro; sin dependencias nuevas.

Dominio nuevo: `backend/apps/tag_portal/`. UI nueva: templates/tag_portal y
css/tag-portal.css. Migración aditiva: `core/0011_tag_portal`. Integración en
modelos/admin/rutas/middleware, login/registro y enlace desde Inicio. Se preservan
las modificaciones previas del usuario y del sprint anterior.

## Verificación final

| Comprobación | Resultado | Evidencia |
|---|---|---|
| Suite SQLite | 91 pruebas; 9 omitidas por requerir PostgreSQL | [sqlite-full.txt](sqlite-full.txt) |
| PostgreSQL + navegador histórico + portal | **93 pruebas, todas pasan** | [postgres-full.txt](postgres-full.txt) |
| Rol runtime restringido | Crear/activar/bloquear sin modificar ledger; fixture revertida | [runtime-role.txt](runtime-role.txt) |
| Navegador portal | Dos contextos aislados, cinco resoluciones, sin errores JS | [browser/result.json](browser/result.json) |
| Firmware esp32dev | Compilación correcta; sin cambios de firmware en este incremento | [firmware.txt](firmware.txt) |
| Configuración | check, makemigrations --check y collectstatic aislado correctos | [config-checks.txt](config-checks.txt) |

La primera ronda de navegador detectó que `Referrer-Policy: no-referrer` producía
Origin null al enviar formularios. Se corrigió a same-origin, conservando CSRF
y evitando envío de referencias a otros orígenes. La evidencia intermedia se
conserva; el resultado final está en postgres-full.txt.

## Alcance y puesta en marcha

Reiniciar `bash scripts/dev-terminals.sh backend` desde firmware/esp32 para
aplicar la nueva migración en la DB de desarrollo del lanzador. Abrir
http://localhost:8000/my/tags/ con una cuenta de esa DB. El alta de enlaces
necesita una tarjeta vinculada mediante el flujo físico existente.

No se migraron las bases personales del usuario durante la validación. Las
pruebas usaron DBs temporales y el servidor PostgreSQL temporal se detuvo al
terminar. No se escribieron tarjetas, generaron fondos, ejecutaron pagos reales,
publicaron cambios ni se hicieron commits.

Las URLs y el tamaño NDEF están preparados; la imagen QR y la grabación física
no se implementaron. Se requieren dominio HTTPS accesible, aprovisionamiento y
pruebas NFC/QR en teléfonos reales. No hay nueva integración Shopify ni firma
Stellar; el POS de comercios y los pagos exclusivos con tag siguen separados.

Guía de operación, decisiones de seguridad y próximos pasos:
[TAG_PORTAL.md](../../docs/TAG_PORTAL.md).
