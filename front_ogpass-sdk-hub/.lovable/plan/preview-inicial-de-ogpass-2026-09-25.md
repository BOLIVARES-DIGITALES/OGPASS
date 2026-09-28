# Preview inicial de OGPASS

## Objetivo
Crear la portada de `ogpass.xyz` como un producto usable con dos accesos principales: **Soy cliente OG** y **Soy desarrollador**.

## Experiencia
- Diseñar una portada móvil y de escritorio con identidad tecnológica propia de OGPASS, enfocada en pagos de transporte y NFC.
- Mostrar dos ventanas grandes y claramente diferenciadas desde el primer vistazo.
- **Cliente OG:** permitir consultar un saldo de demostración con folio o tarjeta, mostrando estado, saldo y movimientos recientes sin revelar datos sensibles.
- **Desarrollador:** presentar una vista de SDK con ejemplo de integración, estado del entorno de pruebas y una consola segura para simular una autorización.
- Incluir navegación interna entre ambas experiencias y estados vacíos, de carga, éxito y rechazo.

## Seguridad
- Mantener toda clave y credencial fuera del navegador y del repositorio público.
- No conectar directamente la interfaz con los endpoints inseguros del sandbox público.
- Usar datos de demostración explícitamente identificados durante esta primera prueba.
- Preparar la estructura para que futuras llamadas privadas pasen por funciones protegidas de Lovable Cloud.

## Lovable Cloud
- Usar el backend ya activado como base para base de datos, almacenamiento, usuarios y funciones privadas.
- En esta fase de preview no se migrarán saldos reales ni se copiarán secretos del repositorio original.

## Entrega
- Reemplazar la pantalla vacía en `/`.
- Añadir metadatos propios de OGPASS.
- Verificar visualmente los dos recorridos en escritorio y móvil.
- Revisar que la aplicación no tenga errores visibles ni fallos de compilación.

## Detalles técnicos
- React/TanStack Start y Tailwind con colores semánticos en el sistema de diseño.
- Componentes accesibles y controles existentes del proyecto.
- El SDK Python/Django/Flask del repositorio se mantiene separado; la UI queda preparada para integrarlo después mediante una API autenticada.
