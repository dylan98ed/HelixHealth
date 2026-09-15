## Context

See `proposal.md` for motivation. The current stack is Django/DRF, PostgreSQL, session authentication with CSRF, and server-rendered HTMX screens. `Professional`, `Specialty`, and `HospitalService` already exist; registration services generate a separate `PR-` registration number and accept license text. Professional JSON routes are still pending. `Admission` persists blood pressure, heart rate, temperature, patient, professional, and creation time. There are no prescription, terminology, exchange, or care-relationship models in the current checkout.

The user confirmed all four image stories, API plus minimal screens, and FHIR R4 XML with a documented profile. The user explicitly deferred license validity checks. The image's story IDs are local to this change: its HU-04 is catalogs, HU-05 registration, HU-06 prescribing, and HU-07 exchange. They are not the similarly numbered stories in `implement-epics-1-and-2`.

Existing changes remain unarchived and `openspec/specs/` is empty. This proposal introduces four distinctly named capabilities instead of pretending that pending delta specs are published main specs. The current uncommitted edits in the older change are not modified by this planning operation.

## Goals / Non-Goals

**Goals:** share transactional domain services between API and HTML; make the requested journeys discoverable for least-privileged users; define interoperable artifacts and import semantics precisely enough for implementation and independent verification.

**Non-Goals:** full FHIR server operations, automatic remote transmission, arbitrary external clinical-resource ingestion, decision support or dosage recommendations, PDF generation, and credential validity checking. Existing unrelated admission behavior remains available; assignment checks govern the newly added prescription/exchange surfaces. Do not revive deferred intervention-note/audit-epic work to implement these features.

## Decisions

### D1. One owner for overlapping work

| Existing work | Treatment when applying this change |
|---|---|
| `add-professional-license-number` | Reuse implemented text validation, forms, and distinct identifiers. No license-expiry/status work. |
| `implement-epics-1-and-2` tasks 8.1-8.2 | Implement missing professional API work once here or reuse it if already completed. Cross-reference overlapping tasks; mark completion only after the shared tests pass. |
| Existing eligibility rollout, including task 8.7 | Finish the supported completed-profile predicate and remove login auto-provisioning as a prerequisite; update affected existing entry points and tests consistently. |
| Existing D6/tasks 9.1-9.7 care relationships | Reuse that model/route design; implement the missing assignment/revocation prerequisite here if still absent. Preserve actor/time, uniqueness, deactivation cleanup, and browser acceptance. |
| Existing active-only professional DNI rule | Superseded by global non-null professional DNI uniqueness in this change, including inactive identities. Patient rules are unaffected. |
| Historical development upgrade scenarios | No compatibility implementation is required; use clean project-owned disposable databases when obsolete state conflicts. Preserve current supported partial-state denial tests. |

At apply time, re-read the changed older artifacts and reconcile only overlapping pending contracts and task references. Do not overwrite their other scheduling decisions. Do not mark unrelated work complete. The alternative of parallel APIs, separate care relationships, or another account-provisioning path would create inconsistent authorization and duplicate implementation.

### D2. Catalog boundaries and model ownership

Keep `Specialty` in `professionals`; expose it through a new `catalogs` app alongside `TerminologyEntry` and `MedicationEntry`. No duplicate specialty table. Keep hospital-service maintenance unchanged; expose a read-only reference list for professional API clients.

Specialties retain `code`, `name`, and `is_active`. Codes are immutable after creation; name and active flag are editable. Normalize whitespace and check names case-insensitively for useful validation, while preserving existing identifiers. Delete only unreferenced rows and return a controlled 409 for protected links. Lock specialty rows consistently with registration to handle deletion/retirement racing a new assignment.

`TerminologyEntry`: system URI, version, code as text, display, source label, created_by, created_at. SNOMED entries use the SNOMED CT system URI and a declared edition/version. Syntax validation checks required fields, identifier format, and lengths; it does not verify membership against a terminology server.

`MedicationEntry`: source system URI, version, code, name, presentation text, optional protected terminology-entry link, source label, created_by, created_at. Presentation describes the catalog item; prescribing dose/directions belong to the prescription item. Enforce a unique `(system, version, code)` tuple for each catalog. No mutable active flag for these append-only tables. Corrections create another source version and selection always shows the version. Clinical issuance snapshots the selected coding and display.

Manual POST and bounded normalized JSON upload call one append-only service. JSON envelope: `{source_label, entries:[...]}`; each row contains the catalog fields above. Limit 500 rows/2 MiB. Return `{created, unchanged}`; compare normalized stored content for existing keys and reject conflicting values with 409 and row indexes. Validate all rows first and insert atomically, handling concurrent uniqueness races without a 500. No URL fetching, RF2 loader, or automatic commercial dataset download. Use synthetic local medication systems in tests; do not label invented codes as SNOMED CT.

Alternative considered: loading full third-party databases during deployment. Deferred because the image permits third-party data but specifies no provider or licensed distribution. The documented normalized upload provides a concrete ingestion path without depending on an unavailable vendor.

### D3. Professional registration and identity

Reuse `register_professional`, update/status services, and the existing HTML forms. Replace `unique_active_professional_dni` with uniqueness for every non-null DNI, and update service conflict lookup, reactivation, and HTTP mappings. Keep canonical ASCII-digit checks. Permit NULL only for a genuinely incomplete profile; it must remain clinically ineligible. The registration contract continues to require active username and hospital service in addition to the image's fields.

License number remains 1..50 trimmed characters. No status, expiry, verification timestamp, registry adapter, or license-currency eligibility predicate is introduced. Registration completeness includes required license input for newly registered profiles. No compatibility bypass for incomplete profiles; signing in never fills missing state.

Registration payload: `username,dni,license_number,first_name,last_name,date_of_birth,specialty_code,hospital_service_code`. Detail retains the previously planned fields: `id,username,dni,license_number,registration_number,first_name,last_name,date_of_birth,specialty_code,hospital_service_code,registration_completed_at,is_active,is_clinically_eligible`, plus a self/detail URL. PATCH allows only license, names, birth date, specialty, and hospital service. Existing incomplete identities can be completed through supported registration, retaining their identity; this is not an upgrade requirement.

### D4. API conventions and discoverability

Use SessionAuthentication and CSRF for unsafe methods. Follow current project response conventions: JSON field errors with 400, anonymous/wrong-role 403, authorized missing target 404, conflict 409, unsupported method 405, body too large 413, wrong upload type 415. Authorize roles before lookup; new clinical patient-specific requests use 404 for missing/unassigned/inactive target to avoid disclosing another patient's record. No new JWT/OAuth scheme is needed for file exchange.

| Route family | Operations and payload/output |
|---|---|
| `/catalogs/api/specialties/`, `/<id>/` | GET/POST collection; GET/PATCH/DELETE detail. DELETE succeeds with 204 only when unreferenced. |
| `/catalogs/api/terminology/`, `/medications/` and `/<id>/` | GET lists/details; POST collection only. `search` filters code/display/name. |
| `/catalogs/api/terminology/import/`, `/medications/import/` | POST normalized JSON; 200 counts after one atomic import. |
| `/catalogs/api/hospital-services/` | GET current service codes/names/active state. |
| `/professionals/api/`, `/search/?dni=...`, `/<id>/` | POST registration (201 new, 200 completion), GET exact search, GET/PATCH detail. Search yields `{results:[]}` or one result including generated number and license. |
| `/professionals/api/<id>/deactivate/`, `/reactivate/` | POST `{confirm:true}`; preserve identifiers, return saved profile. |
| `/patients/api/<id>/care-team/`, `/<relationship_id>/revoke/` | Existing D6 GET/POST and confirmed revoke contracts; assignment by professional DNI. |
| `/clinical-records/api/patients/<id>/prescriptions/` | GET paginated history; POST `{request_key,reason_entry_id?,items:[{medication_id,dose_value,dose_unit,route,frequency,duration_days,instructions?}]}`. 201 new, 200 identical retry. |
| `/clinical-records/api/patients/<id>/prescriptions/<uuid>/` | GET immutable detail with item snapshots and report/XML links. |
| Same prescription detail plus `report/` or `xml/` | GET printable HTML or FHIR XML attachment; return saved issuance content. |
| `/clinical-records/api/patients/<id>/exchange/export/` | POST `{admission_ids:[],prescription_ids:[]}` with at least one selected record; return XML attachment, no domain write. |
| `/clinical-records/api/patients/<id>/exchange/imports/` | GET history; POST multipart `file` with XML plus `source_system` and `request_key`; 201 new, 200 identical retry. |
| Same imports collection plus `/<uuid>/` and `/<uuid>/xml/` | GET import summary/external records and authorized original file retrieval. |

All collection histories use `{count,next,previous,results}`, 20 rows/page and stable ordering. Catalogs sort display/name then ID; histories sort descending clinical/receipt time then ID. Limits: prescription items 1..50; export/import bundles at most 500 entries and 2 MiB, with clear errors requesting a smaller selection. Export IDs are selected by the browser from visible history, never typed manually. Document exact route names, response examples, limits, and file/error content types in OpenAPI. Import is an application upload returning JSON errors, not a FHIR transaction endpoint returning Bundle responses.

Navigation: administrator workspace -> Catalogs -> Specialties/Nomenclature/Medications; existing Professionals registration and maintenance; patient detail -> Care team. Clinical workspace adds an Assigned patients view and patient actions Prescriptions and Interoperability, alongside existing admission navigation. HTML paths mirror these operations under `/catalogs/` and `/clinical-records/patients/<id>/`. Use shared services, ordinary POST/redirect and bound errors; retain HTMX conventions where helpful. The report is escaped printable HTML reachable from prescription detail, not framework administration.

### D5. Prescription persistence, retry, and access

Add `Prescription` and `PrescriptionItem` in a `prescriptions` app. Header: UUID identifier, protected patient/prescriber links, issued_at, doctor-scoped patient request_key and normalized input digest, optional protected reason-entry link, and immutable snapshot JSON. Items: ordered sequence, protected medication link, coding/name/presentation snapshot, decimal dose (positive), nonblank dose unit/route/frequency, integer duration_days (1..365), optional plain instructions (up to 2000 characters). Dose maximum precision is Decimal(12,4); text fields for unit/route/frequency are bounded to 100/100/500 characters. These are input-shape constraints, not clinical appropriateness checks.

Snapshot patient name/DNI/birth date, professional name/DNI/entered license/generated number, institution identifier/name, reason coding, and every item at issue time. Readable report and XML always use that snapshot. Store generated XML bytes for the prescription in the same transaction (database binary/text field, given bounded size) so an issuance cannot succeed with missing/invalid output. Build and validate before commit. No editable draft, cancellation, or correction state machine is included in this change.

Author always comes from the current authenticated account, never a payload field. Check current role/profile/completeness/assignment inside the mutation transaction. Follow shared lock order from D6: User -> Professional -> Specialty -> HospitalService -> Patient -> CareRelationship; new append-only medication/terminology references require no lifecycle locks, then prescription/import records. Sort equal-model rows by PK. Serialize issuance against deactivation/revocation, and define an operation that obtained authorization locks first as allowed to finish. New operations after revocation commits are denied. Report/download routes also recheck access.

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
| B2 professional | Signed-out `/`; administrator; target active login created by supported operator path, no profile/medical role -> Professionals -> Register; fail blank license/duplicate DNI then succeed; detail and DNI search; fresh doctor login. | One profile, distinct numbers, group grant, no staff/credential changes; inactive duplicate denied; license never called verified. |
| B3 assignment | Signed-out `/`; administrator; patient/registered doctor but no relationship -> patient search -> Care team -> DNI lookup -> assign, duplicate submit, revoke/reassign. | Unique active assignment, actor/time, revocation history, no automatic restoration. |
| B4 prescription | Signed-out `/`; eligible assigned doctor; catalog item but no prescription -> Clinical workspace -> Assigned patients -> Prescriptions; invalid input then issuance -> detail/report/XML. | One header/items/snapshots; retry count unchanged; report and independently validated XML match; edited names do not rewrite issuance. |
| B5 vital export | Signed-out `/`; assigned doctor; target admission absent -> existing Record admission form -> history -> Export XML. | Admission saved by UI; exact values/units/author/time in validated XML. |
| B6 external import | Signed-out `/`; assigned doctor; no batch/external records -> patient -> Interoperability -> upload independent matching fixture -> detail -> retry. | External provenance and fields stored once; local admission/prescription counts unchanged. |
| B7 denials | Signed-out `/`; separate no-role, missing-profile, incomplete, inactive, and unassigned accounts; expired session/CSRF and after-revocation requests at HTTP boundary. | No protected clinical output, provisioning, or mutation; safe login redirects and visible denial states. |
| B8 invalid exchange | Signed-out `/`; assigned doctor -> Interoperability -> wrong-patient/invalid fixture; HTTP adversarial XML and concurrent conflicting uploads. | Useful errors, zero partial records/network resolution, deterministic conflicts. |

Use supported provisioning for accounts and unrelated professionals. Fixtures may create unrelated prerequisites; they must not precreate the profile, role, care relationship, admission, prescription, or import that the scenario establishes. Include ordinary POST without JavaScript for new forms, paginated/searchable lists, and navigation visibility by role.

Run focused PostgreSQL HTTP/domain/concurrency tests, existing regression suites, formatting/lint/types, migration drift, and then the repository live validator. Extend both isolated browser journeys and the validator's disposable Compose journeys with persistence verification. Report separately for each environment: signed-out entry point, persona/permissions and state, visible actions, final URL/destination, persisted outcome, executed/passed/skipped browser counts, and exact blockers. Backend security/parser/conformance cases run at real HTTP/integration boundaries; do not substitute direct routes for the visible B1-B6 journeys.

## Risks / Trade-offs

- [FHIR subset mismatch] -> Publish explicit versioned constraints and representative fixtures; reject unsupported input clearly. External exchange requires the peer to use the same profile.
- [Unverified licenses and source institutions] -> Preserve entered/declared values without validity or trust claims; no validity-based blocking was requested.
- [Append-only catalog corrections accumulate versions] -> Show source/version prominently and preserve immutable references. Full terminology lifecycle is deferred.
- [Care-team prerequisite increases work] -> Implement the existing bounded D6 workflow once and reuse it; avoid bypassing patient authorization.
- [Global DNI uniqueness breaks old development data] -> Rebuild only verified project-owned local/test databases; do not add silent merging or historical compatibility branches.
- [Raw XML storage increases database size] -> Enforce file and entry limits; avoid public media and do not log raw clinical payloads.
- [Cross-change drift] -> Reconcile overlapping tasks at apply start and after verification, preserving unrelated edits and deferred work.

## Migration Plan

1. Reconcile overlap, then create migrations from the actual current leaf for global professional DNI uniqueness, catalogs, care relationships if missing, prescription snapshots/items, and import batches/external records.
2. On a clean project-owned PostgreSQL database, apply all migrations; seed only reference/bootstrap roles. Populate synthetic acceptance clinical state through supported workflows. No legacy preservation or conversion work is required.
3. Configure stable institution/identifier values, install pinned validation assets, and run checks plus fresh database migration tests before enabling UI navigation.
4. Run B1-B8 in isolated and disposable Compose environments and verify persisted results. Do not claim the user's running development application was validated by those environments.
5. For local rollback, return code to its prior revision and rebuild the disposable database at the matching schema. Do not remove unrelated project volumes or attempt a destructive reset outside the verified local/test target.
