# Revisión del hato y del rediseño

Fecha: 15 de octubre de 2026. Las pruebas de navegador usaron Django real con
SQLite en memoria, una finca DEMO y animales ficticios. No se modificó Supabase.

## Comprobado

| Recorrido | Resultado |
| --- | --- |
| Acceso con usuario de prueba y descarga inicial | Correcto |
| Buscar por nombre y abrir la ficha | Correcto |
| Modificar nombre y potrero | Guardado local y confirmado en el servidor de prueba |
| Registrar un animal nuevo | Aparece en el hato con su finca y potrero |
| Exportar el hato | CSV de 7 animales; contiene la edición y el animal nuevo |
| Diseño de escritorio y teléfono | Inspección visual a 1280 y 390 px |
| Errores de consola en los recorridos revisados | Ninguno |
| Pruebas automáticas | 21 del backend y 13 del cliente, todas aprobadas |
| Svelte/TypeScript | 0 errores, 0 advertencias |

## Correcciones funcionales

- Los nuevos animales y catálogos conservan la finca al guardarse localmente.
- Las fechas del día usan America/Managua, en vez de la fecha UTC del dispositivo.
- Las dependencias de catálogos se procesan antes de los animales en un mismo lote.
- La ficha busca retiros en todo el historial sanitario, no solo en diez eventos.
- Un tratamiento con cero días de retiro no genera un retiro para ese día.
- El cliente impide encolar colecciones que el rol del usuario no puede guardar.
- El servidor rechaza pesos no positivos y litros negativos.
- El hato y la ficha reaccionan a cambios de datos y al envío de pendientes.
- La interfaz distingue guardado local, pendientes y datos sincronizados.

## Alcance pendiente

Estas pruebas no certifican toda la aplicación. Falta comprobar:

- Recuperación de la sesión al cerrar y reabrir el navegador sin internet.
- Edición simultánea desde dos dispositivos; el sistema actual avisa del conflicto
  y aplica la copia enviada, sin una pantalla para elegir entre versiones.
- Toda la lógica reproductiva, los historiales extensos y las reglas de categorías.
- Rendimiento con el tamaño real del hato y los navegadores usados en campo.
- El empaquetado final de Vercel en Linux: en este equipo Windows el adaptador
  ha fallado al crear enlaces simbólicos. Las comprobaciones de código sí pasan.

## Diseño

Verde bosque, tonos tierra, fondo claro y títulos de estilo editorial. El hato
es la prioridad: búsqueda, filtros, ordenación, acceso directo a editar y estado
de envío visible. En teléfono, los filtros se despliegan cuando se necesitan.

Estos resultados corresponden a las pruebas locales. El resultado del despliegue
se comprueba por separado en los estados de Vercel y Render.
