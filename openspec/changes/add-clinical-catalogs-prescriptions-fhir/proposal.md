## Why

The supplied HU-04 through HU-07 require usable reference catalogs, professional registration, medication prescribing, and exchange of vital signs and prescriptions between institutions. HelixHealth already supports professional registration screens and admission vitals, but professional JSON endpoints, product catalog management, prescriptions, and FHIR exchange are absent.

## What Changes

- HU-04: expose specialty creation, editing, and deletion of unreferenced entries; introduce searchable, append-only SNOMED CT and medication catalogs, with manual entry and bounded third-party data ingestion.
- HU-05: expose professional registration/detail/search/update APIs using the existing services and screens, preserving entered license numbers separately from generated registration numbers. **BREAKING:** reject duplicate professional DNI across active and inactive profiles, replacing the current active-only uniqueness rule.
- User override: license validity checking is deferred. Require the existing nonblank license input, but add no expiry/status fields, verification service, or claim that a credential is current.
- HU-06: allow eligible doctors to prescribe catalog medications to assigned patients and retrieve a human-readable report and FHIR R4 XML prescription file.
- HU-07: export recorded admission vital signs and prescriptions and import supported external FHIR R4 XML records with patient matching, provenance, validation, and duplicate protection.
- Provide minimal administrative and clinical screens reachable from `/`, backed by the same service rules as the APIs.
- Integrate the pending care-assignment workflow as the prerequisite for access to these new patient-specific clinical features; reuse its existing design rather than introducing a second relationship model.

## Capabilities

### New Capabilities

- `clinical-reference-catalogs`: administrative specialty management and append-only terminology/medication catalogs.
- `professional-registration-api`: professional API exposure, consistent global DNI uniqueness, and required unverified license input.
- `medication-prescribing`: assigned-patient prescribing, persisted issuance snapshots, readable reports, and XML downloads.
- `fhir-clinical-exchange`: documented FHIR R4 XML exchange for vital signs and prescriptions, including safe external import and provenance.

### Modified Capabilities

None in `openspec/specs/`, which currently has no published capabilities. Existing related requirements live in unarchived changes; the overlap and precedence are recorded in the design.

## Impact

Affected areas: `professionals`, `clinical_records`, `patients` care-team integration, `access_control`, URL/schema configuration, templates/navigation, and PostgreSQL migrations. New catalog, prescription, and interoperability modules require focused HTTP tests, browser journeys, and isolated/Compose persistence verification. FHIR validation tooling and an XML parser with external entities disabled must be selected and pinned during implementation.

The image is a requirements source, not operational instructions. Its HU numbering differs from `implement-epics-1-and-2`; this proposal uses the image's numbering. Existing user edits to that change remain intact. Overlapping pending API and care-team work must have one implementation owner and shared tests.

Out of scope: checking license validity, a general FHIR server, automatic institution-to-institution transmission, arbitrary procedure/note import, pharmacy dispensing, digital signatures, regulatory certification, full terminology-server operation, and preserving obsolete development database states. The prescription report is printable HTML; PDF is not required.
