# Plan de implementación: intercambio FHIR JSON con prácticas y prescripciones

## Objetivo y alcance

Implementar el intercambio de archivos FHIR R4 JSON para el práctico integrador de
la semana 11. Un `Bundle` de tipo `collection` debe contener un `Patient`, un
`Practitioner`, al menos un `ServiceRequest` y al menos un `MedicationRequest`.
`Observation` es opcional. La importación debe crear o reutilizar pacientes y
profesionales por DNI, incluidos los registros con baja lógica, y asociarles
correctamente las prácticas y prescripciones recibidas.

El intercambio XML existente seguirá disponible. El envío por correo, las
capturas, la Planilla Scrum y la reflexión son entregables académicos externos a
HelixHealth.

## Decisiones de dominio

- Las fichas de pacientes y profesionales tendrán únicamente dos datos nuevos
  de origen: `is_external` y `created_at`. `is_external` será verdadero solo si
  la persona fue creada a partir de una importación. Una persona local
  reutilizada por DNI conservará su valor anterior. Completar o verificar una
  ficha importada no borrará su marca de origen.
- No se agregarán a las fichas campos de sistema de origen, identificador FHIR
  ni lote. El archivo, la fuente declarada y los identificadores externos
  seguirán en los registros técnicos del intercambio cuando sean necesarios
  para validar, auditar, descargar el original y evitar duplicados clínicos.
- Un profesional importado no tendrá acceso a la aplicación por el hecho de
  aparecer en un `Practitioner`. Se debe separar la identidad profesional de
  la cuenta de usuario, o introducir una identidad profesional sin cuenta que
  pueda vincularse mediante el flujo autorizado de alta. La matrícula externa
  no se confundirá con el número de registro local generado por HelixHealth.
- Una ficha creada con datos FHIR podrá estar incompleta. No se inventarán
  teléfono, domicilio, cobertura, especialidad u otros datos ausentes. El flujo
  de completado quedará visible para el rol autorizado. Esto requiere adaptar
  las restricciones actuales de los modelos y sus formularios.
- Reutilizar un registro inactivo por DNI no lo reactivará automáticamente. Si
  sus datos contradicen los del archivo, la importación mostrará el conflicto
  sin crear otra persona ni sobrescribir datos locales de forma silenciosa.
- Las prescripciones importadas se mostrarán junto a las emitidas localmente,
  con una indicación visible de que fueron recibidas. Su representación
  persistente podrá ser una variante explícita del dominio de prescripciones:
  no se deben fabricar ítems de catálogo, datos de emisión o un XML local para
  satisfacer los campos obligatorios de `Prescription`.
- Las prácticas solicitadas (`ServiceRequest`) tendrán entidad propia y estado
  de solicitud. No se presentarán como procedimientos ya realizados.

## Etapas de trabajo

### 1. Contrato FHIR JSON y ejemplos independientes

1. Publicar el perfil de intercambio R4 JSON: cardinalidades, identificadores
   DNI, matrícula en `Practitioner.qualification.identifier`, códigos de
   práctica y medicamento, referencias internas, fechas y límites de archivo.
2. Definir resolución tanto de referencias `urn:uuid:` como de referencias
   relativas `Patient/{id}` y `Practitioner/{id}` dentro del Bundle, sin usar
   esos IDs FHIR como claves de la base local.
3. Definir el tratamiento de `gender=other/unknown`, fechas con y sin hora,
   códigos propios documentados y campos opcionales del ejemplo académico.
4. Preparar un Bundle válido independiente del exportador y variantes inválidas.
   Los valores ficticios del PDF se reemplazarán por identificadores de prueba
   compatibles con las reglas publicadas.

**Criterio de salida:** el perfil y sus archivos de ejemplo explican exactamente
qué acepta y produce HelixHealth; un validador R4 independiente acepta el
ejemplo positivo.

### 2. Modelos, migraciones y conciliación de personas

1. Añadir `is_external` y `created_at` a pacientes y profesionales; mostrar
   ambos datos en sus fichas y búsquedas. Mantener la marca en perfiles
   completados posteriormente.
2. Habilitar perfiles importados incompletos sin conceder roles, cuentas ni
   vínculos asistenciales automáticos.
3. Conciliar DNI usando administradores que incluyan activos e inactivos.
   Revisar las restricciones de unicidad y también las altas normales para que
   ninguna ruta permita duplicar un DNI por una baja lógica.
4. Crear servicios transaccionales de resolución para `Patient` y
   `Practitioner`: reutilizar coincidencia única, crear cuando no exista,
   rechazar ambigüedad o contradicción definida por el contrato.

**Criterio de salida:** nuevas personas quedan marcadas como externas y con
fecha de creación; personas existentes conservan su identidad y estado.

### 3. Prácticas y prescripciones recibidas

1. Modelar una práctica solicitada con código/sistema, descripción, fecha,
   estado, paciente, profesional y procedencia clínica.
2. Representar `MedicationRequest` recibidas sin exigir los invariantes del
   proceso local de emisión. Conservar medicamento, indicaciones, dosis, vía,
   cantidad, notas y fecha cuando existan.
3. Exponer ambas en el historial del paciente y distinguir visualmente los
   registros recibidos de los creados en HelixHealth.
4. Mantener identidad externa estable de cada recurso y la idempotencia de
   importación para evitar duplicados clínicos. Para `Observation`, conservar
   la deduplicación actual y documentar su criterio.

**Criterio de salida:** práctica y prescripción recibidas quedan asociadas a
los IDs locales resueltos del paciente y del profesional, sin convertirse en
una práctica realizada ni una receta emitida localmente.

### 4. Importación FHIR JSON

1. Añadir una entrada visible desde la navegación normal para importar sin
   elegir previamente un paciente. Mantener la entrada XML asociada a un
   paciente mientras se adapta el flujo común.
2. Aceptar `.json` con `application/fhir+json`; limitar bytes, cantidad de
   entradas y profundidad; validar estructura R4, perfil local, identificadores
   y resolución de referencias antes de persistir.
3. Resolver personas y guardar recursos clínicos en una única transacción.
   Reintentos idénticos devolverán el resultado previo; conflictos no dejarán
   personas ni registros parciales.
4. Mostrar un resumen de personas creadas/reutilizadas, estado de baja lógica,
   prácticas y prescripciones incorporadas, errores y acceso protegido al
   archivo original en su formato real.

**Criterio de salida:** un Bundle externo con personas inexistentes puede
importarse desde la interfaz y las asociaciones persistidas son correctas.

### 5. Exportación FHIR JSON

1. Permitir seleccionar para un mismo paciente y profesional al menos una
   práctica solicitada y una prescripción. Conservar las restricciones de
   autorización y pertenencia al paciente.
2. Generar un único Bundle con `Patient`, `Practitioner`, `ServiceRequest` y
   `MedicationRequest`; incluir `Observation` solo si se seleccionan signos
   vitales compatibles. Mantener IDs y referencias estables.
3. Descargar `.json` con `application/fhir+json`. Mantener las opciones XML
   actuales. Documentar la selección y las respuestas en la interfaz y API.

**Criterio de salida:** el JSON descargado supera validación R4 y del perfil,
incluye los cuatro recursos obligatorios y puede importarse en otra instancia.

### 6. Validación final

- Pruebas de integración para JSON válido/inválido, referencias rotas, códigos
  y fechas, límites, permisos, transacciones, reintentos y conflictos.
- Pruebas de navegador desde `/` y sesión cerrada con el menor privilegio
  necesario: personas nuevas, activas e inactivas; profesional sin cuenta;
  datos contradictorios; importación repetida; exportación combinada; y
  `Observation` opcional. Las pruebas crearán las identidades que evalúan
  mediante el recorrido visible, no directamente en la base.
- Verificar las filas persistidas, las asociaciones, `is_external`,
  `created_at`, la falta de permisos para el profesional importado y la
  ausencia de duplicados. Reportar ejecutadas/omitidas y si se probó contra
  servidor aislado o la aplicación de desarrollo/Compose.

## Orden sugerido

Entregar primero el contrato y la conciliación de identidades, luego la
importación JSON completa, y finalmente la exportación combinada. La
validación del recorrido de importación con personas nuevas e inactivas es el
primer hito funcional; la descarga válida que otro sistema puede importar es
el segundo.

## Estado

- Etapa 1: contrato y fixtures independientes en `json-v2/`. El ejemplo
  positivo ya se valida contra el modelo FHIR R4 instalado; las reglas del
  perfil JSON aún no están implementadas en un validador de aplicación.
- Etapa 2: implementada. Las personas recibidas pueden conciliarse por DNI,
  incluso si el registro local está inactivo. Los perfiles nuevos quedan
  marcados como externos y conservan su fecha de creación; los profesionales
  importados no reciben una cuenta ni permisos automáticamente. Las fichas
  muestran el origen y permiten completar o vincular el perfil desde los
  flujos autorizados. La conciliación se verifica por pruebas de integración y
  los recorridos visibles por pruebas de navegador.
- Etapas 3 a 6: pendientes. La importación JSON completa se incorpora en la
  etapa 4; el servicio de conciliación de esta etapa aún no tiene una entrada
  de carga JSON para el usuario.
