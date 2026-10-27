## Purpose

Define the XML exchange requested for HU-08/HU-09: FHIR R4 files for recorded vital signs, medication prescriptions, and plain-text intervention notes/corrections, with reliable patient matching and attributable external records. The existing intervention workflow is owned by `implement-epics-1-and-2`.

## ADDED Requirements

### Requirement: Publish a bounded FHIR R4 exchange profile
The application SHALL document an R4 version 4.0.1 XML collection-Bundle profile covering Patient, Practitioner, Organization, vital-sign Observation, MedicationRequest, and plain-text intervention-note DocumentReference resources. The note profile SHALL require a versioned note type, stable source identifier, patient subject, practitioner author, source-organization custodian, source creation time, exactly one inline UTF-8 text/plain attachment, and a defined `relatesTo=replaces`/correction-reason extension for corrections. It SHALL define required identifiers, supported codes/units, dates, reference resolution, input limits, and error outcomes, with valid and invalid examples. XML downloads SHALL use UTF-8 and `application/fhir+xml`. The application SHALL NOT describe this file exchange as a general FHIR REST server or accept arbitrary procedures, attachments, or intervention resources outside the documented profile.

#### Scenario: Exchange a supported external file
- **WHEN** an external institution supplies a file conforming to the published profile with supported observations, medication requests, and intervention-note DocumentReferences
- **THEN** the application can validate and import it without dependence on its own exporter having produced the file

### Requirement: Export existing vital signs, prescriptions, and intervention notes
A doctor authorized by the existing clinical access rules SHALL export selected saved admission vital signs and issued prescriptions for one active patient. A doctor with current intervention access to that patient SHALL also be able to select existing intervention notes for export. Exported observations SHALL preserve measurement values, units, recorded times, and author references; medication requests SHALL preserve issuance snapshots; note DocumentReferences SHALL preserve immutable text, author, creation time, and complete correction chains with reasons and replacement links. Selection SHALL use visible patient histories and SHALL NOT require manually entering internal identifiers. Exports SHALL contain complete in-bundle references and stable record identifiers. A patient visible in the clinical directory alone SHALL NOT grant intervention-note access.

#### Scenario: Export a recorded admission
- **WHEN** an authorized doctor records an admission through its existing visible form and selects its Export XML action
- **THEN** the resulting bundle contains the recorded blood pressure, heart rate, and temperature with patient and author context and passes the documented profile validation

#### Scenario: Export a corrected intervention
- **WHEN** an eligible assigned professional starts signed out at `/`, signs in, opens the patient's visible intervention history, records a note and correction through that workflow, and selects the chain for XML export
- **THEN** the validated bundle contains both immutable versions with their respective authors/times, plain-text content, correction reason, and an in-bundle `replaces` reference

### Requirement: Resolve the patient and preserve external provenance
Import SHALL target a selected active local patient under existing clinical access rules and require the bundle's patient DNI to match that patient uniquely, with matching birth date. Mismatches, multiple subjects, missing identifiers, or ambiguous identities SHALL be rejected without heuristic matching. An import SHALL record the submitting doctor/time, source institution, external identifiers and authors, and source clinical times. External data SHALL be shown as externally reported and SHALL NOT provision local patients, professionals, roles, or catalog entries, overwrite local admissions, issue local prescriptions, or create/correct local interventions.

#### Scenario: Import and inspect external interventions
- **WHEN** an eligible assigned doctor starts signed out at `/`, signs in, opens an active patient from Clinical workspace, follows Interoperability, uploads an independently authored matching supported XML file containing a note and correction, and opens the import detail
- **THEN** the external observations, prescriptions, and plain-text intervention notes/corrections are persisted and visible with institution, external author, source time, and replacement provenance
- **AND** local admission, prescription, and intervention counts remain unchanged

#### Scenario: Reject the wrong patient
- **WHEN** the uploaded file's DNI or birth date differs from the selected patient, or its clinical records reference another subject
- **THEN** the import returns an identifiable validation error and persists no external clinical records

### Requirement: Atomic import with duplicate and conflict protection
The application SHALL validate the entire import before committing clinical records. Stable source institution and resource identifiers SHALL identify records across uploads. Repeated identical resources SHALL be reused without duplication; conflicting content under an existing source identifier SHALL reject the whole upload with 409. A same-file retry SHALL return the original import result. One invalid clinical entry SHALL prevent all new records in that upload from being saved.

#### Scenario: Retry or mix valid and invalid entries
- **WHEN** a doctor repeats a successful upload, or uploads a bundle with one valid observation and one invalid intervention note/correction
- **THEN** the retry adds no duplicate records, and the mixed invalid bundle adds no records at all

### Requirement: Reject unsafe or unsupported input before side effects
The importer SHALL enforce a 2 MiB file limit and 500-entry limit, reject DTDs/external entities and malformed XML, and perform no network reference resolution. It SHALL reject unsupported resource types, unresolved references, invalid required codes/units, unsupported modifier extensions, or missing clinical fields with useful errors. Note attachments SHALL be inline base64 UTF-8 text/plain only, with 1..4000 trimmed characters; corrections SHALL have a 1..500-character reason and a same-patient/source in-bundle predecessor, without branches or cycles. Source text and narratives SHALL render as inert content. Existing medical authorization and active-patient checks SHALL apply to upload, listing, detail, and retrieval of imported files; note-containing exchanges SHALL also enforce current intervention access.

#### Scenario: Unsafe XML or unauthorized access
- **WHEN** an upload contains external entities or remote references, or an account without clinical access attempts to import or read an import
- **THEN** the request fails without network access, clinical writes, or protected file disclosure

#### Scenario: Deny a note exchange after care access is revoked
- **WHEN** a doctor can still view the patient in the general clinical directory but the care relationship is revoked before a note-containing export, import, detail, or file retrieval
- **THEN** the note operation is denied without disclosing note text or saving external note records

### Requirement: Demonstrate interoperable output beyond a local round trip
Acceptance SHALL include independent FHIR R4/profile validation of generated XML, at least one independently authored valid fixture containing a note and correction, and negative fixtures. A successful export/import round trip alone SHALL NOT be sufficient evidence of conformance.

#### Scenario: Detect a structurally valid but semantically wrong file
- **WHEN** XML has the correct root namespace but contains a wrong vital-sign unit, unresolved medication subject, external note URL, malformed base64/UTF-8, unsupported note type, or dangling replacement link
- **THEN** profile validation rejects it and the import reports the affected resource without partial writes
