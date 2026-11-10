# Contrato propuesto de intercambio FHIR R4 JSON (v2)

Este contrato define el formato de intercambio para el práctico integrador de
semana 11. La carga está disponible en la navegación del profesional médico
como **Import FHIR JSON**. La exportación está en la sección
**Interoperability** de la ficha clínica de cada paciente.
El perfil XML v1 permanece vigente.
FHIR R4 corresponde a la versión 4.0.1; el archivo es UTF-8, termina en
`.json` y se entrega como `application/fhir+json`.

## Exportación

En la ficha de un paciente, un profesional médico activo puede elegir al menos
una práctica solicitada recibida (`ServiceRequest`) y una solicitud de
medicación recibida o receta emitida localmente. También puede elegir una
admisión local para exportar sus tres signos vitales (presión arterial, pulso y
temperatura), aun sin prácticas solicitadas; una receta del mismo profesional
puede incluirse en ese archivo. Se pueden agregar observaciones de signos
vitales importadas en JSON. Todos los registros elegidos deben corresponder al
mismo profesional. Una receta local produce un `MedicationRequest` por ítem.

El botón **Download FHIR JSON** entrega un Bundle `.json` con MIME
`application/fhir+json`. Los IDs de los recursos y el identificador del Bundle
son estables para una misma selección; el `timestamp` refleja la descarga.
El archivo se llama `FHIR_<DNI_paciente>_<DNI_profesional>_<apellido_alumno>.json`:
los DNI provienen del Bundle y el apellido de la cuenta médica que realiza la
descarga. Se eliminan espacios y tildes del apellido para el nombre del archivo.
La exportación es de solo lectura. La selección XML existente sigue separada.

La API ofrece `POST /clinical-records/api/patients/{patient_pk}/exchange/export/json/`
con listas `admission_ids`, `service_request_ids`, `medication_request_ids`,
`prescription_ids` (UUID) y `observation_ids`. Devuelve `200` con el archivo, `400` si faltan
recursos obligatorios o los profesionales no coinciden, `404` si un ID no
pertenece al paciente y deniega cuentas sin perfil médico activo.

## Bundle y recursos

- Un `Bundle` con `resourceType=Bundle`, `type=collection`, `identifier`,
  `timestamp` y entradas con `fullUrl` únicos. Las entradas `request`,
  `search` y `response` no se aceptan.
- Exactamente un `Patient` y un `Practitioner`. Para el intercambio completo
  del práctico se requieren `ServiceRequest` y `MedicationRequest`. Para
  intercambiar signos vitales se acepta al menos un `Observation`, con o sin
  `MedicationRequest`, sin exigir una práctica solicitada. `Organization` es opcional.
  Otros tipos se rechazan en esta versión. Máximo: 500 entradas y 2 MiB.
- `Patient.identifier` debe contener exactamente un DNI argentino de 7 u 8
  dígitos; se lo identifica por el valor aunque el sistema de identificadores
  del emisor sea distinto. También requiere apellido, nombre, `birthDate` y
  `gender`. `male/female/other/unknown` se guardarán como `M/F/O/U` en el
  modelo local. El DNI coincidente se busca entre activos e inactivos.
- `Practitioner.identifier` debe contener exactamente un DNI argentino de 7 u
  8 dígitos; `qualification[].identifier[].value` contiene la matrícula.
  Requiere nombre y apellido. La matrícula se conserva como valor recibido;
  un DNI existente no se duplica aunque el profesional esté inactivo.
- Cada `ServiceRequest` requiere `id`, `status`, `intent`, `code` con sistema y
  código, descripción (`code.text` o `coding.display`), `authoredOn`,
  `subject` y `requester`. Cada `MedicationRequest` requiere además el
  medicamento codificado o en texto, indicaciones en `dosageInstruction`,
  `authoredOn`, `subject` y `requester`. Dosis, vía, cantidad y nota se conservan
  si se proveen. Los sistemas SNOMED CT, LOINC y códigos propios documentados
  son aceptables para prácticas; no se atribuirá un código estándar a un valor
  propio.
- `Observation`, si aparece, requiere `status=final`, paciente, código LOINC,
  `effectiveDateTime` y `valueQuantity` en una unidad UCUM admitida. Se
  conservarán los tres signos vitales admitidos por el perfil XML v1.

## Referencias e identidad

`subject.reference` y `requester.reference` deben resolver al `Patient` y
`Practitioner` del mismo Bundle. Se aceptarán tanto referencias al `fullUrl`
`urn:uuid:<UUID>` como referencias relativas `Patient/<id>` y
`Practitioner/<id>`; no se harán consultas remotas. Los `id` FHIR no son
identificadores de filas locales. Una referencia inexistente o ambigua rechaza
todo el archivo antes de persistir. Los identificadores estables de
`ServiceRequest`, `MedicationRequest` y `Observation`, junto con el emisor,
servirán para detectar reimportaciones y conflictos clínicos.

La comparación de personas usa el DNI, incluso con baja lógica, sin reactivar
ni sobrescribir silenciosamente un registro. La fecha de nacimiento o
matrícula contradictoria se presentará como conflicto. Una persona creada por
importación tendrá `is_external=true` y `created_at`; una persona local
reutilizada conservará `is_external=false`. El archivo y su fuente declarada
podrán conservarse en la bitácora técnica, sin añadirlos a las fichas.

## Fechas y errores

`Patient.birthDate` es una fecha FHIR. `authoredOn` admite fecha o fecha y
hora; si solo hay fecha, se conserva esa precisión, sin inventar una hora.
`effectiveDateTime` de signos vitales debe incluir hora y zona horaria. Se
rechazan JSON malformado, campos obligatorios ausentes, identificadores
ambiguos, referencias rotas, recursos no admitidos y archivos que exceden los
límites. La importación será atómica. Una reimportación idéntica devolverá el
resultado existente; reutilizar una identidad externa con contenido distinto
producirá un conflicto sin escrituras parciales.

## Ejemplos y validación

`fixtures/independent-valid-bundle.json` fue redactado a mano, sin usar el
exportador de HelixHealth. `fixtures/invalid-unresolved-reference.json` y
`fixtures/invalid-ambiguous-dni.json` son casos negativos del perfil local:
ambos pueden ser JSON y recursos FHIR estructuralmente válidos. El ejemplo
del enunciado académico es ilustrativo: sus DNI
ficticios y `urn:uuid:` que no contienen UUID reales no son datos compatibles
con este contrato. El fixture positivo puede comprobarse con el modelo
independiente `fhir.resources` de R4. Esa comprobación confirma la estructura
FHIR general; la validación adicional del perfil local se ejecuta durante la
importación.
La comprobación reproducible es:

```powershell
& .venv/Scripts/python.exe -m pytest interoperability/test_fhir_json_contract.py -q
& .venv/Scripts/python.exe -m pytest interoperability/test_json_importing.py -q
```
