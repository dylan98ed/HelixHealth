## Context

See `proposal.md` for motivation. The current stack is Django/DRF, PostgreSQL, session authentication with CSRF, and server-rendered HTMX screens. `Professional`, `Specialty`, and `HospitalService` already exist; registration services generate a separate `PR-` registration number and accept license text. Professional JSON routes are still pending. `Admission` persists blood pressure, heart rate, temperature, patient, professional, and creation time. There are no prescription, terminology, exchange, or care-relationship models in the current checkout.

The user confirmed all four image stories, API plus minimal screens, and FHIR R4 XML with a documented profile. The user explicitly deferred license validity checks. The image's story IDs are local to this change: its HU-04 is catalogs, HU-05 registration, HU-06 prescribing, and HU-07 exchange. They are not the similarly numbered stories in `implement-epics-1-and-2`.

Existing changes remain unarchived and `openspec/specs/` is empty. This proposal introduces three capabilities: catalogs, prescribing, and clinical exchange. Existing professional work stays owned by its current changes; their artifacts are not modified by this revision.

## Goals / Non-Goals

**Goals:** share transactional domain services between API and HTML; make the requested journeys discoverable for least-privileged users; define interoperable artifacts and import semantics precisely enough for implementation and independent verification.

**Non-Goals:** full FHIR server operations, automatic remote transmission, arbitrary external clinical-resource ingestion, decision support or dosage recommendations, PDF generation, credential validity checking, professional registration/API implementation, changes to DNI uniqueness or eligibility, and care assignment. Reuse existing clinical access and patient discovery. Do not revive deferred intervention-note/audit-epic work to implement these features.

## Decisions

### D1. Reuse existing professional work

| Existing work | Treatment when applying this change |
|---|---|
| `add-professional-license-number` | Reuse implemented text validation, forms, and distinct identifiers. No license-expiry/status work. |
| `implement-epics-1-and-2` tasks 8.1-8.2 | Professional JSON routes remain pending in that change. Do not duplicate them here or make them a prerequisite; new features consume existing domain services directly. |
| Existing eligibility rollout, including task 8.7 | Remains owned by the older change. Reuse the shared clinical access policy available at implementation time without adding a separate completeness gate or changing login provisioning. |
| Existing D6/tasks 9.1-9.7 care relationships | Outside this change. No assignment/revocation workflow, navigation, migration, or access dependency is introduced here. |
| Existing active-only professional DNI rule | Preserve it. No global uniqueness migration or service-policy change is included. Patient rules are also unaffected. |
| Historical development upgrade scenarios | No compatibility implementation is required; use clean project-owned disposable databases when obsolete state conflicts. Preserve current supported partial-state denial tests. |

Repository evidence: `professionals/services.py` implements registration, updates, activation, role assignment, and generated identifiers; `professionals/views.py` and `urls.py` expose the HTML workflows. `professionals/test_views.py` tests persisted registration and CSRF. `professionals/test_services.py` explicitly tests inactive DNI reuse. The route resolver exposes no professional JSON routes, matching pending tasks 8.1-8.2. The new functionality reuses these services and models rather than introducing another registration capability.

At apply time, check the current shared interfaces and reuse them without taking ownership of the older change's pending work. Keep its scheduling and completion records unchanged. Repository evidence establishes the reuse boundary; implementation acceptance still requires the runtime verification in D8.

### D2. Catalog boundaries and model ownership

Keep `Specialty` in `professionals`; expose it through a new `catalogs` app alongside `TerminologyEntry` and `MedicationEntry`. No duplicate specialty table. Keep hospital-service maintenance and professional API reference lookups within the existing professional work.

Specialties retain `code`, `name`, and `is_active`. Codes are immutable after creation; name and active flag are editable. Normalize whitespace and check names case-insensitively for useful validation, while preserving existing identifiers. Delete only unreferenced rows and return a controlled 409 for protected links. Lock specialty rows consistently with registration to handle deletion/retirement racing a new assignment.

`TerminologyEntry`: system URI, version, code as text, display, source label, created_by, created_at. SNOMED entries use the SNOMED CT system URI and a declared edition/version. Syntax validation checks required fields, identifier format, and lengths; it does not verify membership against a terminology server.

`MedicationEntry`: source system URI, version, code, name, presentation text, optional protected terminology-entry link, source label, created_by, created_at. Presentation describes the catalog item; prescribing dose/directions belong to the prescription item. Enforce a unique `(system, version, code)` tuple for each catalog. No mutable active flag for these append-only tables. Corrections create another source version and selection always shows the version. Clinical issuance snapshots the selected coding and display.

Manual POST and bounded normalized JSON upload call one append-only service. JSON envelope: `{source_label, entries:[...]}`; each row contains the catalog fields above. Limit 500 rows/2 MiB. Return `{created, unchanged}`; compare normalized stored content for existing keys and reject conflicting values with 409 and row indexes. Validate all rows first and insert atomically, handling concurrent uniqueness races without a 500. No URL fetching, RF2 loader, or automatic commercial dataset download. Use synthetic local medication systems in tests; do not label invented codes as SNOMED CT.

Alternative considered: loading full third-party databases during deployment. Deferred because the image permits third-party data but specifies no provider or licensed distribution. The documented normalized upload provides a concrete ingestion path without depending on an unavailable vendor.

### D3. Existing clinical access and identity reuse

Use `clinical_records.services.active_professional_for_actor` and the existing medical permission helpers for the new clinical operations. The current policy checks active account, medical role, and active professional profile; active patients are available through the existing clinical directory and search. Require an active selected patient and verify that requested records belong to that patient. Do not introduce care relationships or a separate registration-completeness rule. Reuse the shared predicate if the older change updates it before implementation.

Reuse the existing entered license and separately generated registration number as distinct values in prescription snapshots. Do not change input validation, schema constraints, account provisioning, or identifier generation. Preserve unknown source values as unknown and omit unavailable optional FHIR fields; do not fabricate credentials or add new eligibility conditions to make output fields non-null. Stable FHIR resource identifiers identify the professional independently of optional license/registration-number values. No license status, expiry, verification timestamp, registry adapter, or validity check is introduced.

The catalog screens may modify specialties through their existing model, while registration continues to consume those same references. Keep professional lifecycle tests as regression coverage; do not recreate their implementation or introduce new acceptance criteria for that workflow here.

### D4. API conventions and discoverability

Use SessionAuthentication and CSRF for unsafe methods. Follow current project response conventions: JSON field errors with 400, anonymous/wrong-role 403, authorized missing target 404, conflict 409, unsupported method 405, body too large 413, wrong upload type 415. Authorize roles before lookup; new clinical patient-specific requests use 404 for missing/inactive patients or records outside the selected patient's history. No new JWT/OAuth scheme is needed for file exchange.

| Route family | Operations and payload/output |
|---|---|
| `/catalogs/api/specialties/`, `/<id>/` | GET/POST collection; GET/PATCH/DELETE detail. DELETE succeeds with 204 only when unreferenced. |
| `/catalogs/api/terminology/`, `/medications/` and `/<id>/` | GET lists/details; POST collection only. `search` filters code/display/name. |
| `/catalogs/api/terminology/import/`, `/medications/import/` | POST normalized JSON; 200 counts after one atomic import. |
| `/clinical-records/api/patients/<id>/prescriptions/` | GET paginated history; POST `{request_key,reason_entry_id?,items:[{medication_id,dose_value,dose_unit,route,frequency,duration_days,instructions?}]}`. 201 new, 200 identical retry. |
| `/clinical-records/api/patients/<id>/prescriptions/<uuid>/` | GET immutable detail with item snapshots and report/XML links. |
| Same prescription detail plus `report/` or `xml/` | GET printable HTML or FHIR XML attachment; return saved issuance content. |
| `/clinical-records/api/patients/<id>/exchange/export/` | POST `{admission_ids:[],prescription_ids:[]}` with at least one selected record; return XML attachment, no domain write. |
| `/clinical-records/api/patients/<id>/exchange/imports/` | GET history; POST multipart `file` with XML plus `source_system` and `request_key`; 201 new, 200 identical retry. |
| Same imports collection plus `/<uuid>/` and `/<uuid>/xml/` | GET import summary/external records and authorized original file retrieval. |

All collection histories use `{count,next,previous,results}`, 20 rows/page and stable ordering. Catalogs sort display/name then ID; histories sort descending clinical/receipt time then ID. Limits: prescription items 1..50; export/import bundles at most 500 entries and 2 MiB, with clear errors requesting a smaller selection. Export IDs are selected by the browser from visible history, never typed manually. Document exact route names, response examples, limits, and file/error content types in OpenAPI. Import is an application upload returning JSON errors, not a FHIR transaction endpoint returning Bundle responses.

Navigation: administrator workspace -> Catalogs -> Specialties/Nomenclature/Medications. Clinical workspace uses its existing active-patient directory/search and adds patient actions Prescriptions and Interoperability alongside admission navigation. HTML paths mirror these operations under `/catalogs/` and `/clinical-records/patients/<id>/`. Use shared services, ordinary POST/redirect and bound errors; retain HTMX conventions where helpful. The report is escaped printable HTML reachable from prescription detail, not framework administration.

### D5. Prescription persistence, retry, and access

Add `Prescription` and `PrescriptionItem` in a `prescriptions` app. Header: UUID identifier, protected patient/prescriber links, issued_at, doctor-scoped patient request_key and normalized input digest, optional protected reason-entry link, and immutable snapshot JSON. Items: ordered sequence, protected medication link, coding/name/presentation snapshot, decimal dose (positive), nonblank dose unit/route/frequency, integer duration_days (1..365), optional plain instructions (up to 2000 characters). Dose maximum precision is Decimal(12,4); text fields for unit/route/frequency are bounded to 100/100/500 characters. These are input-shape constraints, not clinical appropriateness checks.

Snapshot patient name/DNI/birth date, professional name/DNI/entered license/generated number, institution identifier/name, reason coding, and every item at issue time. Readable report and XML always use that snapshot. Store generated XML bytes for the prescription in the same transaction (database binary/text field, given bounded size) so an issuance cannot succeed with missing/invalid output. Build and validate before commit. No editable draft, cancellation, or correction state machine is included in this change.

Author always comes from the current authenticated account, never a payload field. Recheck the shared clinical policy and active selected patient inside the mutation transaction. Use existing service locking conventions, ordering relevant User -> Professional -> Patient rows before new prescription/import rows and sorting equal-model rows by PK. Append-only catalog entries require no lifecycle locks. New operations after account/profile/patient deactivation or medical-role removal must fail current access checks; no changes to existing lifecycle services or assignment state are required. Report/download routes also recheck the same access policy.

Enforce unique `(prescriber,patient,request_key)`. A stable key in each HTML form prevents double-click duplication; API clients provide one. Same key plus different canonical payload is 409. Do not infer idempotency from medication content alone, since a doctor may intentionally issue a later identical prescription.

### D6. FHIR R4 collection profile

Use R4 4.0.1 and a self-contained `Bundle.type=collection`. This avoids claiming FHIR document semantics, which would require a Composition. Include unique `fullUrl` URNs and resource IDs, Bundle identifier/timestamp, exactly one Patient, source Organization, required Practitioner context, and one or more supported clinical resources. References resolve inside the bundle only. For this application's v1 profile, allow only these resource types; no server `entry.request` operations.

Document profile constraints and machine-readable StructureDefinitions under `docs/interoperability/fhir-r4/` during implementation. Configure persistent `INTEROPERABILITY_BASE_URI` and institution system/code/name; synthetic local defaults are explicitly for development. Derive stable local identifier systems and profile canonicals from that base. Patient identity uses a documented DNI identifier system; different institutions must agree on it to exchange files. Birth date must also match. Never use local database primary keys as the patient matching contract. Local resource identifiers remain stable across repeat exports.

| Local record | FHIR mapping |
|---|---|
| Admission blood pressure | Observation code LOINC `85354-9`, components `8480-6` systolic and `8462-4` diastolic, UCUM `mm[Hg]`. |
| Admission heart rate | Observation LOINC `8867-4`, UCUM `/min`. |
| Admission temperature | Observation LOINC `8310-5`, UCUM `Cel`. |
| Admission observation context | `status=final`, category `vital-signs`, subject Patient, performer Practitioner, effectiveDateTime from recorded admission time. |
| Prescription item | MedicationRequest with `status=active`, `intent=order`, medicationCodeableConcept from the exact catalog coding, subject, requester, authoredOn, and shared groupIdentifier from the prescription UUID. |
| Medication directions | dosageInstruction.text retains all directions; doseAndRate.doseQuantity stores dose/unit, route.text stores route, timing.code.text stores frequency, timing.repeat.boundsDuration stores duration in days. |
| Optional nomenclature reason | MedicationRequest.reasonCode preserves coding/system/version/display. |

Frequency remains clinician-entered text; do not infer a structured schedule. Unknown external medication codings are retained as external codings and never inserted into the local catalog. External records retain source authors without creating local accounts. Supported incoming Observation values use the listed units and source timezone-aware clinical times; reject unsupported units instead of guessing conversions. Incoming MedicationRequests must meet the same required direction fields and use supported `active`/`order` semantics in v1; reject other states explicitly. External status is displayed as a source claim, never converted into a local executable prescription.

FHIR XML requires ordered elements in its namespace, primitive value attributes, and the FHIR XML MIME type. [HL7 R4 XML](https://hl7.org/fhir/R4/xml.html) defines these serialization rules. [HL7 R4 Bundle](https://hl7.org/fhir/R4/bundle.html) defines collection resources and references. [HL7 R4 vital signs](https://hl7.org/fhir/R4/observation-vitalsigns.html) supplies the Observation codes/units. [HL7 R4 MedicationRequest](https://hl7.org/fhir/R4/medicationrequest.html) defines one medication per request. The narrower supported input subset, limits, patient matching, and application permissions above are project decisions.

### D7. Import isolation, validation, and provenance

Add an `interoperability` app with `ImportBatch` (UUID, patient, submitted_by, received_at, declared source_system, normalized bundle digest, request_key, raw XML, summary) and `ExternalClinicalRecord` (patient, source_system, resource_type, external identifier system/value, immutable normalized content/digest, source times/authors, clinical kind). A batch-to-record relationship supports reused entries. Unique source/resource identifiers prevent duplicate clinical entries across different bundles; include patient identity in semantic conflict detection, not in a way that would silently permit one source ID to identify two patients.

Pipeline: authorize selected patient -> check content type and byte/entry/depth limits (depth 64) -> parse with DTD/entities/network disabled -> validate R4 plus v1 profile -> match patient -> resolve all references -> normalize records -> lock/recheck access -> atomically create/reuse batch and external records. Raw files stay in the database behind authorized endpoints, not in public media. Never resolve schema locations or URLs from input. Ignore executable narrative rendering; display only escaped extracted text. Reject unsupported extensions in v1 with explicit errors, including all modifier extensions.

Declare `source_system` via the upload field and require it to match the Organization identifier in the bundle. This records asserted provenance, not verified institutional identity or a cryptographic signature. Bundle identifiers and normalized digests provide same-file retry recognition; the request key also detects conflicting retry content. Deduplicate clinical resources by source/type/identifier after canonical extraction, independent of XML whitespace and bundle-local URN choices. Identical content is reused; changed content under the same source identity rejects the entire upload. Corrections require new external identifiers in this profile version.

Export local records only in v1; imported records remain readable and their original file is downloadable. Receiving external observations does not create an Admission because that would fabricate a local consultation and author. Receiving a MedicationRequest does not issue a local prescription. This preserves attribution while satisfying the requested receive/import workflow.

Select and pin XML validation dependencies after checking Python 3.13 support during implementation. Use bundled official R4 schema resources and an explicit profile validator at runtime, with an independent HL7-compatible validator in acceptance/CI to check invariants and profiles. Check in an independently authored external fixture; do not rely solely on exporter-to-importer agreement. A dependency or validator that cannot run is a validation blocker, not a reason to claim FHIR conformance from well-formed XML alone.

### D8. Acceptance and evidence

| Journey | Initial state and visible path | Persisted/observable evidence |
|---|---|---|
| B1 catalogs | Signed-out `/`; non-staff administrative account -> Catalogs; create/edit/delete unused specialty, add nomenclature/medication, upload duplicate and invalid catalog data. | Correct list/version data, append-only enforcement, protected deletion, atomic import counts. |
| B2 prescription | Signed-out `/`; doctor authorized by current clinical policy; catalog item but no prescription -> Clinical workspace -> active patient -> Prescriptions; invalid input then issuance -> detail/report/XML. | One header/items/snapshots; retry count unchanged; report and independently validated XML match; edited names do not rewrite issuance. |
| B3 vital export | Signed-out `/`; authorized doctor; target admission absent -> existing Record admission form -> history -> Export XML. | Admission saved by UI; exact values/units/author/time in validated XML. |
| B4 external import | Signed-out `/`; authorized doctor; no batch/external records -> active patient -> Interoperability -> upload independent matching fixture -> detail -> retry. | External provenance and fields stored once; local admission/prescription counts unchanged. |
| B5 access policy | Signed-out `/`; realistic medical and nonmedical accounts, including relevant missing/incomplete/inactive-profile states; expired session/CSRF and deactivated patient requests at HTTP boundary. | New features follow the existing shared eligibility outcome for each state; denied requests disclose no clinical output or perform writes. No new completeness or assignment gate. |
| B6 invalid exchange | Signed-out `/`; authorized doctor -> active patient -> Interoperability -> wrong-patient/invalid fixture; HTTP adversarial XML and concurrent conflicting uploads. | Useful errors, zero partial records/network resolution, deterministic conflicts. |

Use supported provisioning for accounts and unrelated professionals. Registration is prerequisite setup through its existing supported path, not a new workflow under test here. Fixtures must not precreate the catalog entry, admission, prescription, or import that a scenario establishes. Include ordinary POST without JavaScript for new forms, paginated/searchable lists, and navigation visibility by role. Keep existing professional tests as regression coverage.

Run focused PostgreSQL HTTP/domain/concurrency tests, existing regression suites, formatting/lint/types, migration drift, and then the repository live validator. Extend both isolated browser journeys and the validator's disposable Compose journeys with persistence verification. Report separately for each environment: signed-out entry point, persona/permissions and state, visible actions, final URL/destination, persisted outcome, executed/passed/skipped browser counts, and exact blockers. Backend security/parser/conformance cases run at real HTTP/integration boundaries; do not substitute direct routes for the visible B1-B6 journeys.

## Risks / Trade-offs

- [FHIR subset mismatch] -> Publish explicit versioned constraints and representative fixtures; reject unsupported input clearly. External exchange requires the peer to use the same profile.
- [Unverified licenses and source institutions] -> Preserve entered/declared values without validity or trust claims; no validity-based blocking was requested.
- [Append-only catalog corrections accumulate versions] -> Show source/version prominently and preserve immutable references. Full terminology lifecycle is deferred.
- [Raw XML storage increases database size] -> Enforce file and entry limits; avoid public media and do not log raw clinical payloads.
- [Shared clinical policy changes in another change] -> Reuse the current predicate and test the same outcomes on new endpoints; do not duplicate its rollout or introduce a separate policy.

## Migration Plan

1. Create migrations from the actual current leaf for catalogs, prescription snapshots/items, and import batches/external records. Preserve professional identity constraints and existing authorization workflows.
2. On a clean project-owned PostgreSQL database, apply all migrations; seed only reference/bootstrap roles. Populate synthetic acceptance clinical state through supported workflows. No legacy preservation or conversion work is required.
3. Configure stable institution/identifier values, install pinned validation assets, and run checks plus fresh database migration tests before enabling UI navigation.
4. Run B1-B6 in isolated and disposable Compose environments and verify persisted results. Do not claim the user's running development application was validated by those environments.
5. For local rollback, return code to its prior revision and rebuild the disposable database at the matching schema. Do not remove unrelated project volumes or attempt a destructive reset outside the verified local/test target.
