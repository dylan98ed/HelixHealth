## Purpose

Define HU-07 FHIR R4 XML file exchange of recorded vital signs and medication prescriptions, with reliable patient matching and attributable external records.

## ADDED Requirements

### Requirement: Publish a bounded FHIR R4 exchange profile
The application SHALL document an R4 version 4.0.1 XML collection-Bundle profile covering Patient, Practitioner, Organization, vital-sign Observation, and MedicationRequest resources. It SHALL define required identifiers, supported codes/units, dates, reference resolution, input limits, and error outcomes, with valid and invalid examples. XML downloads SHALL use UTF-8 and `application/fhir+xml`. The application SHALL NOT describe this file exchange as a general FHIR REST server or accept arbitrary intervention resources outside the documented profile.

#### Scenario: Exchange a supported external file
- **WHEN** an external institution supplies a file conforming to the published profile with supported observations and medication requests
- **THEN** the application can validate and import it without dependence on its own exporter having produced the file

### Requirement: Export existing vital signs and prescriptions
An eligible assigned doctor SHALL export selected saved admission vital signs and issued prescriptions for one patient. Exported observations SHALL preserve measurement values, units, recorded times, and author references; medication requests SHALL preserve issuance snapshots. Selection SHALL use visible patient history and SHALL NOT require manually entering internal identifiers. Exports SHALL contain complete in-bundle references and stable record identifiers.

#### Scenario: Export a recorded admission
- **WHEN** an assigned doctor records an admission through its existing visible form and selects its Export XML action
- **THEN** the resulting bundle contains the recorded blood pressure, heart rate, and temperature with patient and author context and passes the documented profile validation

### Requirement: Resolve the patient and preserve external provenance
Import SHALL target a selected authorized local patient and require the bundle's patient DNI to match that patient uniquely, with matching birth date. Mismatches, multiple subjects, missing identifiers, or ambiguous identities SHALL be rejected without heuristic matching. An import SHALL record the submitting doctor/time, source institution, external identifiers and authors, and source clinical times. External data SHALL be shown as externally reported and SHALL NOT provision local patients, professionals, roles, care relationships, or catalog entries, overwrite local admissions, or issue local prescriptions.

#### Scenario: Import and inspect external interventions
- **WHEN** an assigned doctor starts signed out at `/`, signs in, opens an assigned patient, follows Interoperability, uploads a matching supported XML file, and opens the import detail
- **THEN** the external observations and prescriptions are persisted and visible with institution, external author, and source time
- **AND** local admission and prescription counts remain unchanged

#### Scenario: Reject the wrong patient
- **WHEN** the uploaded file's DNI or birth date differs from the selected patient, or its clinical records reference another subject
- **THEN** the import returns an identifiable validation error and persists no external clinical records

### Requirement: Atomic import with duplicate and conflict protection
The application SHALL validate the entire import before committing clinical records. Stable source institution and resource identifiers SHALL identify records across uploads. Repeated identical resources SHALL be reused without duplication; conflicting content under an existing source identifier SHALL reject the whole upload with 409. A same-file retry SHALL return the original import result. One invalid clinical entry SHALL prevent all new records in that upload from being saved.

#### Scenario: Retry or mix valid and invalid entries
- **WHEN** a doctor repeats a successful upload, or uploads a bundle with one valid observation and one invalid medication request
- **THEN** the retry adds no duplicate records, and the mixed invalid bundle adds no records at all

### Requirement: Reject unsafe or unsupported input before side effects
The importer SHALL enforce a 2 MiB file limit and 500-entry limit, reject DTDs/external entities and malformed XML, and perform no network reference resolution. It SHALL reject unsupported resource types, unresolved references, invalid required codes/units, unsupported modifier extensions, or missing clinical fields with useful errors. Source text and narratives SHALL render as inert content. Medical authorization and care access SHALL apply to upload, listing, detail, and retrieval of imported files.

#### Scenario: Unsafe XML or unassigned access
- **WHEN** an upload contains external entities or remote references, or an unassigned doctor attempts to import or read an import
- **THEN** the request fails without network access, clinical writes, or protected file disclosure

### Requirement: Demonstrate interoperable output beyond a local round trip
Acceptance SHALL include independent FHIR R4/profile validation of generated XML, at least one independently authored valid fixture, and negative fixtures. A successful export/import round trip alone SHALL NOT be sufficient evidence of conformance.

#### Scenario: Detect a structurally valid but semantically wrong file
- **WHEN** XML has the correct root namespace but contains a wrong vital-sign unit or unresolved medication subject
- **THEN** profile validation rejects it and the import reports the affected resource without partial writes
