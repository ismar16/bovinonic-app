# Revisión funcional: formularios, catálogos y lotes

Fecha: 16 de octubre de 2026.

Las pruebas del navegador usaron una finca DEMO con SQLite en memoria y ocho animales ficticios. No se ingresaron datos de prueba en Supabase.

## Cambios

- Potreros, propietarios y fierros tienen listados, altas y edición en vistas independientes dentro de Catálogos. La edición conserva sus identificadores y relaciones con el hato.
- Lotes tiene listado, ficha y formulario para agregar o quitar animales existentes. Cada animal tiene como máximo un lote; lote y potrero son independientes.
- Ingreso de varios animales permite hasta 200 filas, omite filas vacías, detecta aretes repetidos y aplica lote, potrero, propietario y fierro comunes. El guardado local usa una sola transacción.
- El hato permite filtrar por lote; las fichas y el formulario individual muestran la asignación. El CSV incluye lote, potrero, propietario y fierro.
- Formularios de animales, estado, pesaje, ordeño, sanidad, reproducción y usuarios usan el mismo diseño, con etiquetas, errores, bloqueo de doble envío y confirmación de guardado.
- Reportes, alertas y ajustes usan la presentación de la finca. El acceso rápido se oculta durante la captura para no tapar botones en teléfono.
- Las rutas protegidas restauran la sesión antes de mostrar sus datos. Una sesión verificada recientemente puede abrir los datos locales cuando la API no responde; un rechazo explícito del servidor no habilita ese acceso.
- La sincronización admite reintentos después de una caída temporal de la API. Conserva pendientes cuando falla el envío o se intenta cambiar de sesión.
- El servidor valida fechas, sexo/categoría, progenitores y pertenencia de lotes a la finca. Al modificar un tratamiento se recalcula o elimina su fecha de retiro.
- La renovación de sesión guarda también la cookie de renovación rotada. Crear usuarios valida la contraseña y evita asociar una cuenta existente por coincidencia de nombre.

## Comprobaciones

| Recorrido | Resultado |
| --- | --- |
| Crear lote con dos animales existentes | Guardado y confirmado en la API local |
| Registrar dos animales nuevos en ese lote | Cuatro integrantes, sin cambiar el potrero de los anteriores |
| Arete repetido en ingreso de varios | Error visible; no guarda parcialmente |
| Editar integrantes del lote | Añadir y retirar confirmados en la API |
| Editar propietario: nombre, identificación y teléfono | Listado y API muestran los cambios |
| Registrar tratamiento, pesaje y servicio | Guardado local y confirmación en la API |
| Actualizar un ordeño del mismo día y turno con 9,25 L | Un único registro, actualizado a 9.25 L |
| Exportar hato | CSV de ocho animales, cuatro con lote y doce columnas |
| Recargar la interfaz con la API detenida | Conserva la sesión y muestra los ocho animales en modo campo |
| Revisión móvil de 11 vistas | Sin desbordamiento horizontal a 320 px; revisión visual adicional a 390 px |
| Vista de lotes en escritorio | Revisada a 1280 px |
| Errores de consola en los recorridos con API activa | Ninguno |
| Pruebas automáticas | 28 de Django y 22 del cliente aprobadas |
| Svelte/TypeScript | Sin errores ni advertencias |
| Migraciones | Sin cambios de modelo pendientes de generar |

La compilación local genera cliente, servidor y service worker. El empaquetado del adaptador de Vercel falla en Windows por permisos para crear enlaces simbólicos (EPERM). El empaquetado de producción se verifica por separado en Vercel, que usa Linux.

## Límites de la revisión

- No se certifica toda la lógica ganadera ni el rendimiento con el volumen real de producción.
- La prueba de desconexión detuvo la API; queda probar instalación y reapertura completamente sin red en los teléfonos de campo.
- La escritura local de una operación es indivisible. El envío se divide en grupos de 20 registros y puede completarse en varias solicitudes; los pendientes se conservan para reintentar.
- Los conflictos entre dispositivos siguen aplicando la última copia enviada y mostrando un aviso; no hay selector de versiones.
- El registro de un servicio calcula fechas orientativas, no confirma preñez.
- La edición de eventos históricos de producción, sanidad y reproducción no está incorporada en esta entrega; la edición completa solicitada para catálogos y composición de lotes sí está disponible.
- El despliegue debe ejecutar la migración `livestock.0004` antes de utilizar lotes. El comando de construcción de Render ya incluye `migrate --noinput`.
