# Registro de ventas y cobros

## Flujo implementado

1. Entrar en **Operaciones → Ventas y cobros → Registrar venta**, desde Hato o desde la ficha del animal.
2. Indicar comprador, teléfono opcional, fecha, moneda, animales, peso de venta en kg y precio por kg. Cada animal puede tener su precio.
3. Revisar importes y, si existe un acuerdo activo, gastos y liquidación individual. Agregar solamente gastos posteriores que no estén ya en el acuerdo.
4. Guardar. La venta permanece pendiente hasta recibir confirmación del servidor. Al confirmar, los animales pasan a vendidos conservando su historial, propietario y lote.
5. En el detalle, registrar cobros al comprador: fecha, importe, medio y referencia. Admite pagos parciales hasta completar el total. El reparto entre propietario y responsable es un saldo calculado, no un pago entre ellos.
6. Consultar historial, filtrar por comprador, arete o saldo, y descargar un comprobante CSV con animales, gastos, liquidación y abonos.

## Acuerdos con ventas parciales

- Se liquida cada animal vendido y los demás permanecen en curso.
- Gastos específicos: se descuentan únicamente del animal indicado.
- Gastos comunes originales: partes iguales entre los animales originales. Los centavos restantes se asignan por su orden original; nunca se duplican gastos entre ventas.
- Desde la primera venta se protegen condiciones, animales y gastos originales del acuerdo. Los gastos posteriores se registran en la venta del animal correspondiente.
- El peso inicial pertenece al propietario; se descuentan gastos de la ganancia y se reparte el resto, reconociendo quién adelantó los gastos. Las pérdidas requieren confirmación expresa.
- Al vender el último animal, el acuerdo queda liquidado. Sus totales suman los comprobantes individuales y conservan su redondeo.
- Pasto alquilado: conserva el cálculo de gastos y reembolsos, sin reparto del valor de venta.
- No se modifica ni se convierte la moneda del acuerdo.

## Integridad y sincronización

- Servidor autoritativo: recalcula importes, valida finca, rol, animales activos, fechas y versión del acuerdo. Venta, salida del hato y liquidación se confirman en una transacción.
- Ventas y abonos confirmados son inmutables. Reintentos con el mismo UUID no duplican ventas, gastos ni cobros.
- Una venta no puede repetirse para el mismo animal y un abono no puede superar el saldo. Las escrituras se serializan por finca, incluidos distintos dispositivos.
- Solo el administrador accede a ventas, cobros y liquidaciones.
- Las operaciones pendientes se conservan localmente; una corrección de pendiente consulta primero el comprobante del servidor para recuperar respuestas perdidas. Los datos confirmados prevalecen.
- El nuevo almacenamiento local se añade sin borrar registros reales ni pendientes anteriores. No se ejecutó ninguna limpieza en producción.

## Alcance de esta entrega

- Venta por peso en kg y precio por kg; importe positivo, hasta dos decimales. Total máximo por venta: 999,999,999.99 en la moneda seleccionada.
- No incluye facturación fiscal, impuestos, conversión de monedas, anulación/devolución de ventas confirmadas ni registro de transferencias entre los participantes del acuerdo.
- Registros históricos marcados como vendidos antes de este módulo se conservan; no se inventan compradores, importes ni cobros retroactivos.
- La migración `livestock.0006` crea únicamente tablas e índices; no altera ni elimina registros existentes.
- Preparado localmente para revisión; esta entrega no se desplegó en producción.


## Gastos posteriores a una venta confirmada

En **Ventas y cobros → abrir venta → Agregar gasto a esta venta** se elige animal, fecha real del gasto, concepto, importe y quién lo pagó. El registro admite un gasto olvidado anterior a la fecha de venta, siempre que no sea futuro ni anterior al nacimiento del animal.

El gasto se guarda como un asiento independiente e inmutable, con UUID y fecha de registro. Se conserva el comprobante original; la liquidación actual se deriva del original y todos los gastos posteriores, sin duplicarlos al sincronizar. El resumen del acuerdo también se actualiza cuando ya estaba cerrado. No cambian comprador, peso, precio, total de venta, cobros ni saldo del comprador.

Los gastos pendientes muestran un cálculo provisional y admiten revisión antes de confirmarse; se comprueba primero el registro del servidor para recuperar respuestas perdidas. Si el nuevo gasto genera pérdidas, se exige confirmación expresa del reparto. En ventas propias se muestra el ingreso menos gastos; en pasto alquilado se actualiza el reembolso al responsable. El comprobante CSV incluye gastos posteriores y liquidación original y actualizada.
