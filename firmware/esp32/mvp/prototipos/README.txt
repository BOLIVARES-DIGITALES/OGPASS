OGPASS — LABORATORIO DE PROTOTIPOS
Fecha: 2026-10-11
Estado: ITERATE. Ninguna ficha implica soporte comercial ni prueba física realizada.

Objetivo
Gobernar IDEA → PROTOTIPO → PRUEBA → EVIDENCIA → EVALUACIÓN → PRODUCTIZACIÓN.

Hardware
Hardware propio o expresamente autorizado, inventariado por modelo y revisión.

Protocolo
Cada protocolo tiene namespace y contrato versionado; no se mezclan balances ni redes.

Mini driver
OgpassReader: begin/health/detect/read/write/emulate/capabilities/reset; registrar en ReaderManager.

Capacidades
Declarar lo implementado; UNSUPPORTED para operaciones pendientes. No inferir capacidades por marca del chip.

Arquitectura
Drivers → adaptadores → normalizador → identidad. Wallet y ledger mantienen sus servicios actuales.

Pruebas
Unitarias, banco, integración, UX, estabilidad, consumo y revisión de seguridad; repetir entre reinicios y nodos.

Resultados
Las pruebas de software viven fuera de prototipos. Ver evidence/launch-20261011. Aquí solo .txt.

Riesgos
Un experimento aislado no demuestra estabilidad, seguridad, compatibilidad ni fondos reales.

Criterio de promoción
PROMOTE requiere evidencia y aprobación operativa del gate 07; ITERATE si hay pendientes; REJECT si no es viable.

Decisión actual: ITERATE
