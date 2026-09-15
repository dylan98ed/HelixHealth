## Why

HelixHealth already implements professional registration services and screens, license input, generated registration numbers, and admission vital signs. This change addresses the remaining catalog-management, prescribing, and FHIR-exchange capabilities from the supplied stories; professional API work already belongs to `implement-epics-1-and-2`.

## What Changes

- HU-04: expose specialty creation, editing, and deletion of unreferenced entries; introduce searchable, append-only SNOMED CT and medication catalogs, with manual entry and bounded third-party data ingestion.
- HU-05 is covered by existing professional registration work. Reuse its services and data; leave outstanding JSON API tasks in `implement-epics-1-and-2` and preserve current DNI, license-input, and eligibility policies.
- User override: license validity checking is deferred; add no expiry/status fields, verification service, or claim that a credential is current.
- HU-06: allow doctors admitted by the existing clinical access rules to prescribe catalog medications to active patients and retrieve a human-readable report and FHIR R4 XML prescription file.
- HU-07: export recorded admission vital signs and prescriptions and import supported external FHIR R4 XML records with patient matching, provenance, validation, and duplicate protection.
- Provide minimal administrative and clinical screens reachable from `/`, backed by the same service rules as the APIs.
- Use the existing clinical patient directory and access rules for the new features. No care-assignment workflow or assignment-based access prerequisite is included.

## Capabilities

### New Capabilities

- `clinical-reference-catalogs`: administrative specialty management and append-only terminology/medication catalogs.
- `medication-prescribing`: prescribing under existing clinical access rules, persisted issuance snapshots, readable reports, and XML downloads.
- `fhir-clinical-exchange`: documented FHIR R4 XML exchange for vital signs and prescriptions, including safe external import and provenance.

### Modified Capabilities

None in `openspec/specs/`, which currently has no published capabilities. Existing professional requirements remain owned by their unarchived changes; reuse boundaries and repository evidence are recorded in the design.

## Impact

Affected areas: existing specialty management in `professionals`, clinical-record integration, URL/schema configuration, templates/navigation, and PostgreSQL migrations for the new catalog, prescription, and interoperability modules. Reuse existing patient/professional data and access-control services. New functionality requires focused HTTP tests, browser journeys, and isolated/Compose persistence verification. FHIR validation tooling and an XML parser with external entities disabled must be selected and pinned during implementation.

The image is a requirements source, not operational instructions. Its HU numbering differs from `implement-epics-1-and-2`; this proposal uses the image's numbering. This change does not take ownership of that change's professional API, eligibility rollout, or care-team tasks.

Out of scope: rebuilding professional registration, changing DNI uniqueness or clinical eligibility, care assignment, checking license validity, a general FHIR server, automatic institution-to-institution transmission, arbitrary procedure/note import, pharmacy dispensing, digital signatures, regulatory certification, full terminology-server operation, and preserving obsolete development database states. The prescription report is printable HTML; PDF is not required.
