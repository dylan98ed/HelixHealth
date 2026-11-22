# Plan de implementación de la épica 3 · Turnos médicos e historia clínica electrónica

El objetivo es que recepción pueda ofrecer, reservar y seguir un turno, y que el profesional autorizado pueda consultar y ampliar la historia clínica electrónica (HCE) del paciente. El alcance acordado comprende 12 historias (HU-11 a HU-15 y HU-17 a HU-23). Se excluyó la asignación automática de la HU-16. El paciente elige el profesional y el horario entre las opciones que le ofrece recepción en la HU-14. En la HU-15, recepción registra manualmente el canal de origen y la respuesta que dio por ese medio. La integración con WhatsApp queda fuera del alcance.

## Punto de partida y orden de entrega

HelixHealth ya cuenta con padrones de pacientes, profesionales y especialidades, un equipo tratante por paciente, admisiones con signos vitales, prescripciones locales y registros clínicos importados. La agenda puede reutilizar esos padrones. La HCE puede reunir los registros desde sus módulos de origen y usar el vínculo asistencial vigente para controlar el acceso.

| Entrega | HU | Resultado que permite validar |
| --- | --- | --- |
| 1. Agenda y reserva manual | HU-12 → HU-13 → HU-14 → HU-11 | Administración abre horarios. Recepción encuentra un horario libre, identifica al paciente, lo reserva y ve el turno en la agenda. |
| 2. Operación de recepción | HU-18, HU-15 y HU-17 | Recepción gestiona solicitudes y registra llegadas, ausencias y cancelaciones. El paciente recibe el recordatorio de su turno confirmado. |
| 3. Historia clínica | HU-19 → HU-20 y HU-22 → HU-21 | El médico abre la HCE de un paciente a cargo, registra la atención y consulta su evolución junto a los datos de los demás módulos. |
| 4. Consulta de auditoría | HU-23 | Un usuario autorizado reconstruye los cambios. El registro de eventos de esta HU se implementa en la entrega 3, junto con cada operación de escritura. |

Las prioridades indicadas abajo son las de la consigna. Se proponen bloques de duración configurable por profesional y correo electrónico para el recordatorio.

## Permisos de la épica

| Función | Operaciones habilitadas |
| --- | --- |
| Recepción | Usar un grupo «Recepción» en el esquema de roles existente para consultar la agenda, cotejar identidades, gestionar solicitudes y turnos y registrar llegadas, ausencias y cancelaciones. Resolver la búsqueda por DNI desde la agenda con los datos identificatorios y de contacto necesarios. Una cuenta de recepción puede operar con ese único grupo. |
| Administración de agendas | Configurar horarios y excepciones mediante el permiso específico de HU-12. |
| Médico tratante | Con cuenta y perfil médico activos y vínculo asistencial vigente, leer la HCE del paciente, registrar consultas y evoluciones y gestionar sus antecedentes. Comprobar estas condiciones en cada lectura y escritura. |
| Consulta de auditoría | Con permiso explícito, el administrador habilitado puede consultar la trazabilidad de la HCE. Para el profesional habilitado, el alcance se limita a sus pacientes con vínculo vigente. El permiso es de solo lectura. |

Reservar, reasignar, cancelar o marcar un turno como atendido conserva la composición del equipo tratante. Si un profesional recién elegido necesita acceder a la HCE, el operador autorizado debe asignarlo mediante el flujo existente de equipo tratante. Los permisos de recepción y configuración de agendas por sí solos no habilitan las funciones de HCE ni de auditoría de esta épica.

## Agenda y turnos

### HU-11 · Consultar la agenda diaria — Alta

**Pasos**

1. Agregar la entrada «Agenda diaria» al inicio de recepción. Abrir en la fecha local de hoy y permitir elegir día y profesional.
2. Ordenar los turnos por hora y mostrar paciente, profesional y estado con una etiqueta de texto. Distinguir pendiente, confirmado, atendido, cancelado y ausente. Mantener las cancelaciones visibles aunque el horario vuelva a ofrecerse.

**Pruebas**

- Preparar turnos en los cinco estados mediante los flujos de reserva, confirmación y asistencia. Abrir la agenda como recepcionista y comprobar horarios, orden y las cinco etiquetas.
- Cambiar de profesional y día, incluyendo un día sin citas. Verificar que cada selección muestre solo sus turnos y que una fecha vacía se identifique como tal.
- Cambiar el estado de un turno en otra sesión, actualizar la agenda y verificar el valor guardado.

### HU-12 · Configurar horarios y disponibilidad — Alta

**Pasos**

1. Dar al administrador un permiso específico para configurar agendas. Permitir seleccionar profesional, días de atención, hora de inicio y fin, duración del turno, vigencia y excepciones por fecha.
2. Validar rangos y superposiciones para el mismo profesional, incluso entre reglas con vigencias coincidentes. Aceptar franjas contiguas.
3. Aplicar cambios desde su fecha de vigencia. Conservar los turnos registrados con su horario, profesional y estado, e indicar al administrador cuáles quedan fuera del nuevo horario. Descontar siempre las reservas vigentes al calcular disponibilidad.

**Pruebas**

- Crear dos franjas contiguas y comprobar los horarios ofrecidos. Intentar guardar una franja invertida y otra parcialmente superpuesta. Ambas deben mostrar el error y conservar la configuración anterior.
- Con un turno confirmado para el próximo lunes, acortar la jornada desde ese lunes y bloquear otro día. Verificar que el turno original siga en la agenda y que los horarios retirados dejen de ofrecerse para nuevas reservas.
- Entrar como recepcionista y verificar que pueda consultar la agenda y que el servidor rechace un intento de modificar la configuración.

### HU-13 · Registrar, modificar y cancelar turnos — Alta

**Pasos**

1. Crear el turno con paciente, profesional, inicio, fin y estado. Desde recepción, permitir reservar, reprogramar y cancelar con constancia de quién realizó la operación y cuándo.
2. El horario de un profesional queda ocupado en cuanto se guarda la reserva, incluso si el turno queda pendiente de confirmación del paciente. Registrar una solicitud, consultar el horario u ofrecérselo al paciente deja el horario libre. Validar la disponibilidad del profesional elegido y guardar la reserva en una misma transacción de PostgreSQL.
3. Al reprogramar, liberar el horario anterior solo al asegurar el nuevo. Al cancelar, conservar el registro y volver a ofrecer el intervalo si sigue siendo futuro y hábil.

**Pruebas**

- Reservar, reprogramar y cancelar desde recepción. Reabrir la agenda tras cada operación y verificar el paciente, el horario ocupado o liberado, el estado y la constancia de cancelación.
- Intentar mover una cita a un horario ocupado. Debe mostrarse el conflicto y la cita original debe seguir reservada.
- Hacer competir dos sesiones por el mismo profesional e intervalo, también con solapamiento parcial. Verificar una sola reserva vigente, un aviso de conflicto para la otra sesión y que otro profesional pueda atender en ese horario.

### HU-14 · Buscar disponibilidad y validar la identidad — Alta

**Pasos**

1. Mostrar a recepción una lista de horarios por especialidad y fecha, con el nombre del profesional junto a cada horario y un filtro opcional por profesional. Usar las reglas de HU-12 y la ocupación de HU-13 para ofrecer solo intervalos futuros, completos y libres de profesionales habilitados. Recepción selecciona la opción que elige el paciente.
2. Antes de confirmar, buscar al paciente por DNI, mostrar los datos identificatorios pertinentes y solicitar a recepción que coteje un segundo dato, por ejemplo la fecha de nacimiento. Ante una discrepancia, permitir corregir la búsqueda.
3. Al guardar la reserva, comprobar en el servidor que el intervalo siga disponible y asociar el turno al paciente identificado. Al confirmar un turno pendiente, verificar la identidad, el estado del paciente y la vigencia de esa misma reserva.

**Pruebas**

- Desde `/`, iniciar sesión con una cuenta que solo pertenezca a «Recepción», abrir la agenda, identificar al paciente por DNI y fecha de nacimiento y guardar la reserva. Comprobar que el resultado de la búsqueda solo contenga datos de identificación y contacto, y que el servidor deniegue a esa cuenta tanto la ficha administrativa con datos clínicos como la HCE del paciente.
- Buscar una especialidad con dos profesionales y combinar los tres filtros. Contrastar los resultados con la agenda, incluyendo un turno ocupado, una excepción de horario y un profesional inactivo.
- Con dos médicos libres a la misma hora, seleccionar al segundo de la lista. Verificar que la reserva corresponda al médico elegido y que el horario del primero siga disponible.
- Con dos pacientes homónimos, confirmar con DNI y fecha de nacimiento coincidentes. Verificar el paciente asociado al turno. Repetir con dato discordante, paciente inactivo e intento de omitir la validación. Ninguno debe confirmar.
- Ocupar el horario desde otra sesión entre la búsqueda y el guardado de la reserva. Verificar que recepción vea el conflicto y las alternativas vigentes, y que reservar otra opción requiera una nueva selección.

### HU-15 · Registrar solicitudes y confirmarlas por el canal de origen — Media

**Pasos**

1. Dar a recepción una bandeja para registrar paciente, contacto, canal de origen (teléfono o WhatsApp), preferencia de turno y estado de la solicitud. Una solicitud puede quedar pendiente aunque todavía carezca de horario.
2. Al guardar la reserva, vincular la solicitud con un único turno de HU-13. Si el paciente confirma después, aplicar la verificación de HU-14 y actualizar ese mismo turno. Registrar manualmente el resultado del contacto por el mismo medio, el operador y la fecha. Mantener pendientes los intentos sin respuesta.

**Pruebas**

- Registrar una llamada, salir y volver a abrir la bandeja. Confirmar por teléfono y verificar que queden asociados solicitud, turno, canal y operador.
- Con dos sesiones de recepción y un único profesional disponible, registrar una solicitud y ofrecer un horario desde la primera. Verificar desde la segunda que aún se ofrece. Guardar la reserva como pendiente y comprobar que el horario desaparece de la lista de opciones. Confirmar y verificar que el mismo turno sigue ocupándolo. Cancelar y comprobar que el horario futuro vuelve a ofrecerse.
- Repetir con una solicitud recibida por WhatsApp y una respuesta gestionada manualmente. Registrar primero un intento sin respuesta y luego la confirmación. Verificar la transición y que repetir el guardado conserve un solo turno.

### HU-17 · Recordar al paciente su turno 24 horas antes — Media

**Pasos**

1. Calcular el vencimiento del recordatorio a partir del inicio del turno. Ejecutar una tarea periódica que seleccione turnos confirmados cuando falten 24 horas o menos y la atención siga siendo futura. Una confirmación dentro de esa ventana queda disponible para el próximo envío.
2. Enviar al correo del paciente la fecha, la hora local y el profesional. Registrar el resultado por turno y horario. Revalidar estado y horario antes de enviar, descartar avisos pendientes obsoletos y habilitar el recordatorio de la nueva fecha al reprogramar.
3. Registrar los fallos de entrega, reintentar errores transitorios y hacer visible a recepción un contacto faltante o inválido para que pueda resolverlo.

**Pruebas**

- Fijar el reloj y ejecutar la tarea antes del umbral, exactamente a 24 horas y después del umbral. Verificar en un buzón de prueba un único mensaje con destinatario y horario correctos. Confirmar otra cita una hora antes de la atención y comprobar que reciba un recordatorio en la siguiente ejecución y ninguno adicional al repetirla.
- Probar turnos pendientes, cancelados, atendidos, ausentes y pasados. Reprogramar uno con un aviso en espera. Comprobar que solo se entregue el aviso correspondiente a un turno confirmado con el horario vigente.
- Simular un fallo de correo, recuperar el servicio y repetir la tarea. Comprobar la entrega y el registro de intentos sin duplicados. Con un paciente sin correo, verificar que el fallo quede visible y que los demás envíos continúen.

### HU-18 · Registrar asistencia, ausencia o cancelación — Alta

**Pasos**

1. Cuando el paciente se presenta, recepción coteja su identidad como en HU-14 y usa «Registrar asistencia». Esa acción pasa el turno de **pendiente** o **confirmado** directamente a **atendido** y registra la llegada. El médico documenta la consulta en la HCE mediante HU-20. Habilitar «Registrar ausencia» una vez alcanzada la hora de atención y usar la cancelación de HU-13 cuando corresponda.
2. Guardar actor, fecha, estado anterior y nuevo. Reflejar el cambio en la agenda y proteger los estados finales frente a envíos repetidos o desactualizados.

**Pruebas**

- Con tres citas confirmadas, registrar asistencia, ausencia y cancelación respectivamente. Volver a abrir la agenda y verificar los tres estados y sus constancias.
- Con un turno pendiente, intentar registrar la llegada con un dato identificatorio discordante y comprobar que siga pendiente. Corregir el dato y registrar la asistencia en una acción. Verificar que el mismo turno figure como atendido y que su historial contenga una única transición de pendiente a atendido, con operador y fecha.
- Registrar la llegada antes de que el médico abra la consulta. Verificar de inmediato que la agenda muestre «Atendido» y que la HCE conserve sus registros previos. Luego guardar la consulta como médico y comprobar que aparezca una única consulta nueva con su autor y que el turno siga atendido.
- Intentar marcar ausencia antes de la hora. Después, intentar cancelar desde una pantalla que otro operador dejó abierta antes de registrar asistencia. Comprobar el rechazo y que se conserve el último estado válido.

## Historia clínica electrónica

### HU-19 · Acceder a la historia clínica del paciente — Alta

**Pasos**

1. Incorporar «Historia clínica» al recorrido del médico desde su panel y la lista de pacientes a cargo. Identificar al paciente por nombre y número de historia antes de mostrar sus antecedentes y registros asistenciales.
2. Reutilizar el equipo tratante y verificar rol médico, perfil habilitado y vínculo vigente tanto en el resumen como en los detalles. Mostrar un estado vacío comprensible para el paciente que aún carezca de registros.

**Pruebas**

- Asignar un paciente por el flujo administrativo de equipo tratante. Ingresar como su médico, abrir la HCE desde el panel y verificar identidad, antecedentes y una admisión conocida. Repetir con un paciente asignado sin registros.
- Con otro médico sin vínculo, comprobar la restricción en la navegación y en el acceso directo al detalle. Revocar la asignación con la HCE abierta y verificar que la siguiente lectura quede denegada. Cubrir también perfil inactivo y cuenta sin rol médico.
- Reservar un turno con un médico ajeno al equipo tratante, confirmar y registrar la llegada. Verificar que el médico siga sin acceso de lectura o escritura a esa HCE. Asignarlo por el flujo de equipo tratante y comprobar que pueda acceder. En otro turno, cancelar la reserva de un médico ya asignado y verificar que conserve su vínculo.

### HU-20 · Registrar una consulta y su evolución clínica — Alta

**Pasos**

1. Desde la HCE, abrir «Nueva consulta» en el contexto del paciente. Guardar fecha, motivo y evolución inicial, tomando al profesional responsable de la sesión autenticada.
2. Permitir incorporar notas de evolución fechadas a esa consulta. Conservar la autoría de cada nota y registrar el cambio en la auditoría de HU-23. Mostrar la consulta al volver a la HCE.

**Pruebas**

- Abrir la HCE de un paciente asignado, registrar una consulta y añadir una evolución. Reingresar y comprobar el contenido, el orden, el paciente y la autoría. Verificar que la HCE de un segundo paciente conserve sus propios registros.
- Enviar el formulario sin los datos obligatorios y repetirlo tras revocar el vínculo. Verificar el error y la ausencia de escrituras parciales. Intentar sustituir al profesional en la petición y comprobar que jamás se atribuya la atención a un tercero.

### HU-21 · Consultar cronológicamente signos vitales, prescripciones y prácticas — Alta

**Pasos**

1. Reunir por paciente las admisiones con signos vitales, las prescripciones emitidas y los registros externos disponibles de observaciones, medicación y solicitudes de prácticas. Incorporar las consultas de HU-20 y conservar el enlace al detalle autorizado de cada fuente.
2. Ordenar toda la lista por fecha clínica, de más reciente a más antigua, antes de paginar. Mostrar tipo, procedencia, fecha y profesional responsable cuando consten. Identificar por separado al registrador administrativo cuando corresponda. Conservar la precisión de las fechas de origen e identificar los datos faltantes.
3. Para prácticas, mostrar las órdenes importadas existentes como «Práctica solicitada», con su fecha de solicitud y su profesional solicitante cuando consten. El alcance de esta entrega se limita a consultar esas órdenes.

**Pruebas**

- Registrar signos vitales, emitir una receta e importar una orden de práctica con fechas intercaladas. Usar una orden recibida hoy pero emitida antes de la receta. Verificar orden clínico, valores, responsable y procedencia. Comprobar que la orden aparezca una sola vez como «Práctica solicitada», con la fecha y el solicitante de origen.
- Probar fechas iguales, cambio de página, una admisión sin profesional responsable y una fecha externa sin hora. Verificar orden estable, ausencia de duplicados y representación fiel de los datos disponibles. Los eventos de un segundo paciente deben quedar fuera del listado y de sus enlaces.

### HU-22 · Registrar, consultar y actualizar antecedentes personales y familiares — Media

**Pasos**

1. Incorporar en la HCE dos categorías identificables, personal y familiar. Permitir al médico tratante agregar antecedentes, indicar parentesco cuando corresponda y consultar lo ya registrado.
2. Permitir actualizar un antecedente seleccionado. Guardar su versión vigente, el profesional y la fecha de modificación, y conservar la revisión anterior para HU-23.

**Pruebas**

- Registrar un antecedente personal y otro familiar con parentesco. Reabrir la HCE, editar el familiar y verificar que se muestre el nuevo valor, que el personal siga intacto y que el cambio figure en auditoría.
- Intentar guardar un antecedente vacío, editar uno de otro paciente y actualizar con un vínculo revocado. Verificar que se conserven los datos previos.

### HU-23 · Consultar la trazabilidad de las modificaciones de la HCE — Alta

**Pasos**

1. Usar el módulo de auditoría para registrar cada alta o modificación que alimente la HCE. Instrumentar las escrituras de consultas, evoluciones y antecedentes, además de las entradas provenientes de admisiones, prescripciones e importaciones. Guardar el evento en la misma transacción que el cambio.
2. Identificar paciente, registro, operación, fecha, actor u origen y valores modificados o referencias a sus versiones. Preservar el historial y ofrecer una vista de solo lectura, filtrable por paciente, fecha y tipo de registro.
3. Otorgar el permiso de consulta a administradores habilitados y profesionales expresamente autorizados. Para un profesional, comprobar además el alcance por paciente. Separar este permiso del que usa recepción para operar la agenda.

**Pruebas**

- Crear una consulta y corregir un antecedente. Como administrador habilitado, filtrar por paciente y reconstruir quién hizo cada cambio, cuándo y qué valor cambió. Repetir como profesional autorizado dentro de su equipo tratante.
- Verificar un evento de origen local y otro importado. Forzar el fallo de una escritura antes de confirmar y comprobar que se reviertan el cambio y su evento. Un reenvío de una operación ya aplicada debe conservar una única traza de ese cambio.
- Intentar leer el historial desde recepción, como profesional sin permiso y como auditor profesional fuera del equipo tratante. Verificar la denegación también en el servidor. Comprobar que la interfaz y los permisos de la aplicación preserven los eventos frente a edición o borrado.

## Validación de cada entrega

- **Recorrido en navegador.** Comenzar en `/` con una sesión nueva y cerrada para cada rol. Autenticarse, verificar el destino y operar con enlaces, formularios y datos conocidos por el usuario, como DNI o matrícula. Crear cuentas, permisos y vínculos mediante sus flujos habilitados. Preparar por fuera del recorrido solo los datos ajenos a lo que se quiere demostrar.
- **Resultado persistido.** En agenda, seguir una misma cita desde la configuración de disponibilidad hasta su estado final. En HCE, seguir un paciente desde su asignación al equipo tratante hasta la consulta de su evolución y auditoría. Reabrir cada resultado en otra sesión autorizada y contrastarlo con PostgreSQL. Para HU-17, comprobar también el mensaje recibido en el buzón de prueba.
- **Casos que requieren integración.** Ejecutar las carreras de reservas con conexiones independientes sobre PostgreSQL y las pruebas de recordatorios con reloj controlado y servicio de correo de prueba. Usar el navegador para verificar cómo se comunican al operador los conflictos y los resultados.
- **Evidencia de cierre.** Por HU, registrar punto de entrada, rol y permisos, estado inicial, acciones visibles, destino final y resultado persistido. Informar cuántas pruebas de navegador se ejecutaron y cuántas se omitieron. Identificar por separado la ejecución en servidor aislado y en la aplicación de desarrollo con Compose. Documentar cualquier recorrido pendiente y su bloqueo.
