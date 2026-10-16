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

## Reinicio autorizado de datos de prueba

El reinicio se prepara con `reset_test_data` en modo de consulta y se ejecuta
solamente con `--execute`, la finca concreta, el usuario a conservar y los
conteos esperados. Conserva la contraseña del administrador, vacía los datos
operativos, elimina los otros usuarios y reemplaza nombre y ubicación de prueba.
No crea respaldos. El proceso es transaccional y rechaza instalaciones con más
de una finca o conteos distintos a los revisados.

Cada reinicio incrementa una versión de datos. La sincronización consulta esa
versión antes de enviar pendientes; al detectar un reinicio, descarta la copia
local anterior y descarga la finca vacía. Las versiones anteriores de la
aplicación no pueden subir registros con un marcador antiguo. El servidor
bloquea reinicio y escrituras concurrentes usando la misma fila de finca.
Las copias en dispositivos desconectados se limpian cuando vuelven a conectarse
con la versión actualizada de la aplicación.

Validación adicional: pruebas de simulación, ejecución y cancelación del
reinicio; bloqueo de clientes antiguos y permisos del estado de sincronización;
limpieza de pendientes antes de subirlos, conservación de nuevos datos,
reintentos sin red y rechazo de retrocesos de versión. Resultado: 33 pruebas
Django y 26 del cliente aprobadas; Svelte/TypeScript sin diagnósticos.

## Envío automático después de guardar

Un guardado local confirmado programa un intento de sincronización después de
1,5 segundos sin nuevos guardados. Los cambios consecutivos se agrupan. Si hay
un envío o cambio de sesión en curso, el intento espera a que termine; una
edición guardada durante un envío se manda en el siguiente. El retorno de la
conexión, volver a una pestaña visible y el temporizador de 60 segundos también
activan intentos. Una falla conserva los pendientes y no genera un bucle de
reintentos inmediatos. Los temporizadores y suscripciones se eliminan al cerrar
la interfaz. El tiempo total de confirmación depende de la respuesta del servidor.

Pruebas del cliente: 31 aprobadas, incluidas agrupación de guardados, cambios
durante una subida lenta, reconexión, retorno a la aplicación, intento periódico
y cancelación de temporizadores. Los formularios indican el envío automático.

## Acuerdos de manejo en otras fincas

Se incorporan acuerdos independientes de la propiedad y de los lotes de manejo,
con propietario, responsable, finca externa, moneda NIO/USD, fechas, condiciones,
animales y gastos pagados. Las modalidades son ganancia de peso, valor completo
de venta, valor de venta de crías y pasto alquilado. El reparto físico de crías y
el cálculo automático del alquiler por mes/cabeza no forman parte de esta entrega.

La ganancia de peso conserva un peso inicial individual y usa pesos/precios
finales por animal. Los gastos se descuentan antes del reparto y se reembolsan a
quien los pagó. El valor inicial corresponde al propietario. Los totales de las
dos partes suman el valor de venta; los redondeos conservan los centavos. El
servidor calcula con Decimal y el cliente con enteros BigInt; comparten siete
casos de prueba, incluidos pérdidas, porcentajes distintos y centavos impares.
El cierre con saldo negativo requiere una confirmación explícita que se renueva
al modificar datos del cálculo.

El acuerdo se sincroniza como una unidad indivisible. El servidor valida finca,
animales, importes, fechas y gastos; rechaza animales en dos acuerdos en curso y
bloquea modificaciones después de liquidar. La liquidación del servidor ignora
los totales calculados enviados por el cliente. Los acuerdos y sus importes se
reservan al administrador. El hato identifica la finca externa mientras el
acuerdo está en curso y la ficha conserva los enlaces a su historial.

Las liquidaciones no ejecutan pagos ni marcan animales como vendidos. Los gastos
son importes efectivamente pagados e ingresados manualmente; no se importan
tratamientos sanitarios sin costo. Un acuerdo con varios animales se liquida
completo; para liquidaciones independientes se crea uno por animal. Puede
descargarse un CSV con condiciones, pesos, precios, gastos y liquidación.

Comprobado en navegador con una finca DEMO y SQLite en memoria:

- Crear un acuerdo, tomar el peso inicial del historial y enviarlo automáticamente.
- Filtrar el animal en otras fincas y abrir el acuerdo desde su ficha.
- Editar, agregar un gasto médico, liquidar y confirmar en la API local.
- Ejemplo de 180 a 280 kg, C$100/kg y C$1.000 de medicamentos: saldo C$9.000,
  partes C$4.500; total propietario C$23.500 y responsable C$4.500.
- Exportar el CSV y verificar esos importes en el archivo descargado.
- Pasto alquilado: gasto adelantado por el responsable de C$500, reembolso C$500,
  sin reparto de ganancia ni pesos de venta obligatorios.
- Bloqueo de la ruta de edición de un acuerdo liquidado.
- Renovación de la confirmación de pérdida al cambiar un precio.
- Listado, captura con animales/gastos, detalle y cierre a 320 px sin desbordamiento;
  revisión visual del detalle de liquidación a 1280 px.

Estas pruebas no introdujeron registros ficticios en producción. Validación:
41 pruebas Django, 35 del cliente y comprobación Svelte/TypeScript.


## Ventas y cobros — 16/10/2026

Implementado el plan de PLAN_VENTAS.md. Ventas de uno o varios animales con comprador, fecha, moneda, kg, precio individual y gastos adicionales; comprobantes CSV, historial y filtros por saldo. Abonos append-only con control de saldo y recuperación de pendientes consultando el recibo autoritativo. El estado Vendido se registra desde Ventas y se protege de reactivaciones cuando existe comprobante confirmado.

Acuerdos: liquidación por animal con gastos específicos y reparto igualitario de gastos comunes, asignando centavos de forma estable. Se protegen condiciones y gastos originales desde la primera venta; los gastos posteriores se cargan en la siguiente venta. El último animal cierra el acuerdo y sus totales suman los recibos individuales. Las actualizaciones parciales cambian updated_at para su descarga incremental. Las ventas no registran pagos entre las partes: los abonos son cobros al comprador.

Verificación:
- Backend: 54 pruebas correctas, incluidas ventas duplicadas, atomicidad y rollback del inventario, ventas parciales, gastos/pérdidas, reintentos, permisos, recuperación de recibos y cobros sin exceder el saldo. Migraciones sin cambios pendientes.
- Frontend: 41 pruebas correctas; cálculos coincidentes con servidor, asignación de centavos, restricciones de ventas, conservación de pendientes, corrección sin duplicar registros y recuperación de respuestas perdidas.
- Svelte/TypeScript: 0 errores y 0 advertencias.
- Navegador con API SQLite en memoria: primera venta 280 kg × C$100 = C$28,000, gasto común asignado C$500.01, propietario C$23,250.01 y responsable C$4,749.99; segundo animal 300 kg × C$100 = C$30,000, gasto C$500.00. Acuerdo final C$58,000, gastos C$1,000.01, propietario C$47,500.01 y responsable C$10,499.99. Abono C$10,000 confirmado y saldo C$18,000 en la primera venta.
- Formulario y detalle revisados a 320 px, sin desbordamiento horizontal; revisión visual de escritorio a 1280 px.
- Datos exclusivamente ficticios en API de prueba aislada. No se modificó la base de producción ni se desplegó esta entrega.

Límites de esta entrega: ventas por kg, sin facturación fiscal, conversión monetaria ni anulaciones de ventas o abonos confirmados. El historial previo marcado como vendido se conserva sin inventar importes retroactivos. Ver PLAN_VENTAS.md para alcance y recorrido.
