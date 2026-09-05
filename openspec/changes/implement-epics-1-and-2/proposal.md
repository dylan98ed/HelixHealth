## Why

HelixHealth implements the OpenHIS-UNLaM educational hospital workflow: identify patients, record admissions, maintain professionals, and permit traceable clinical work for assigned patients. Patient management and admission already exist; the remaining work needs explicit contracts so an implementing agent can extend them without inventing identity, authorization, or migration rules.

## What Changes

- Preserve HU-01/HU-02 patient lifecycle and HU-03 admissions, including immutable identifiers/events, concurrency protections, exact-DNI search, and pagination.
- Extend the existing professional identity in place for HU-04/HU-05: complete registration, deterministic educational license verification and history, maintenance, search, deactivation, and verified reactivation.
- **BREAKING at HU-04 rollout:** medical group membership and an incomplete legacy profile will no longer grant clinical access. Preserve existing profile IDs and admissions; an application administrator completes the profile and verifies its license. Preserve intentionally inactive profiles until explicit reactivation.
- Provide the minimal supporting workflows for HU-06: administrators assign/revoke patient care relationships; assigned professionals record or correct a plain-text intervention note. Corrections preserve the original note.
- Audit intervention reads/writes and authorization denials, with defined handling for anonymous actors, nonexistent targets, concurrent revocation, and unavailable audit storage.
- Make remaining tasks independently reviewable with concrete contracts, prerequisites, files, tests, and signed-out browser acceptance journeys.

## Capabilities

### New Capabilities

- `patient-management`: HU-01 through HU-03 patient lifecycle, bounded lists/history, admission validation, and integration with verified clinical identity.
- `professional-management`: HU-04 through HU-06 professional lifecycle, educational license verification, exact-DNI lookup, care assignments, minimal intervention notes/corrections, and append-only auditing.

These remain the two new capability deltas of the existing change; this revision adds no capability files.

### Modified Capabilities

None outside this change.

## Impact

- Extend professionals, access_control, clinical_records, and audit; integrate care-team navigation with patients and the shared templates.
- Keep the existing Python/Django/DRF/PostgreSQL modular monolith, sessions, HTMX/Bootstrap, locked dependencies, Gunicorn/WhiteNoise production configuration, and disposable Compose validation.
- Add additive migrations, explicit API/form contracts, synthetic reference data, and acceptance coverage for both fresh databases and incomplete legacy profiles.
- Account/password administration stays in Django Admin for an authorized operator. Product workflows use their own interfaces.
- Exclude appointments, billing, beds, prescriptions, diagnosis coding, external license-registry integration, FHIR, general account self-registration, a full clinical chart, and admission amendments. The local registry is educational and is not evidence of real-world licensure.

Implementation decisions and the deliberate legacy-access transition are in design.md; execution order and completion gates are in tasks.md.
