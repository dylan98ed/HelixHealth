## 1. Existing-service integration and setup

- [x] 1.1 Confirm the existing professional services, specialty model, clinical access helpers, and patient directory interfaces described in D1-D3. Verify the integration reuses them and leaves professional API tasks, eligibility rollout, DNI policy, and care-team work in their existing change without duplicating or making them prerequisites here.
- [x] 1.2 Establish the `catalogs`, `prescriptions`, and `interoperability` module boundaries and settings/test discovery additions. Verify Django checks and existing test collection succeed without placeholder routes claiming implemented functionality.
- [x] 1.3 Select and pin Python 3.13-compatible safe XML parsing, local R4 validation assets, and independent FHIR/profile validation tooling. Verify installation and validation of one independently authored valid fixture plus rejection of one invalid fixture; record exact versions and offline/no-network runtime behavior.

## 2. HU-04 reference catalogs

- [x] 2.1 Add terminology and medication models with D2 source/version identities, metadata, protected links, and constraints. Verify PostgreSQL uniqueness/required-field tests and fresh migration application; preserve the existing Specialty table.
- [x] 2.2 Implement specialty create/edit/retire/delete services with immutable codes and protected deletion. Verify duplicate input, referenced deletion, and concurrent registration versus retirement/deletion produce controlled results without broken links.
- [x] 2.3 Implement append-only catalog creation and normalized JSON ingestion with size/row bounds, exact-repeat reuse, and atomic conflicting-row rejection. Verify repeated keys inside one upload, concurrent imports, invalid rows, and no partial writes in PostgreSQL tests.
- [x] 2.4 Add catalog APIs with D4 statuses, read/write roles, CSRF, search, and pagination. Verify real HTTP requests cover exact payloads, 20-row pages, denied roles, and 405 update/delete for immutable catalogs; disable framework-admin mutation bypasses.
- [ ] 2.5 Add Catalogs navigation, specialty forms/confirmation, nomenclature/medication entry forms, and JSON upload/results screens. Verify B1 starts at signed-out `/`, uses a non-staff administrator, persists all intended changes through visible controls, and exercises ordinary POST without JavaScript.

## 3. FHIR R4 contract and export components

- [ ] 3.1 Deliver `docs/interoperability/fhir-r4/` profile documentation, machine-readable constraints, identifier conventions, configured institution values, and independent positive/negative fixtures. Verify the independent validator accepts the supported R4 examples and rejects mismatched codes, units, references, and unsupported resource types.
- [ ] 3.2 Implement safe serialization and in-bundle reference generation for Patient, Practitioner, Organization, and admission Observations using D6 codes/units. Verify official R4/profile validation, stable identifiers, correct recorded times, escaping, UTF-8 MIME headers, and no unintended record writes.
- [ ] 3.3 Implement MedicationRequest and prescription bundle serialization from issuance snapshots, including grouping, dosage fields, and optional reason coding. Verify multi-item output with the independent validator and assert every represented patient/prescriber/medication value matches the supplied snapshot.

## 4. HU-06 prescriptions and outputs

- [ ] 4.1 Add prescription/item models, immutable snapshots, request-key constraints, and stored XML field. Verify clean migrations, protected references, positive doses/durations, unique item order, and no mutable framework-admin surface.
- [ ] 4.2 Implement atomic issuance from the authenticated prescriber with D5 access locks, item validation, snapshot capture, and validated XML generation before commit. Verify spoofed fields, unknown medication, invalid directions, inactive patients or denied clinical access, and serializer failure leave no partial prescription.
- [ ] 4.3 Implement request-key replay/conflict handling and history/detail/report/XML endpoints. Verify identical concurrent retry creates one prescription, changed retry returns 409, post-issuance patient/professional edits preserve report/XML content, and unauthorized retrieval discloses no clinical output.
- [ ] 4.4 Add patient Prescriptions list, medication selection, issuance form, detail, printable report, and XML download controls. Verify B2 from signed-out `/`, invalid-then-valid input, multiple items, ordinary POST, repeated submit, final destinations, downloaded content, and persisted counts.

## 5. HU-07 external import and patient exchange

- [ ] 5.1 Add import batches, external clinical records, batch membership, source identities/digests, and protected raw-file storage. Verify database uniqueness and that external authors/data require no local patient, account, role, catalog, Admission, or Prescription creation.
- [ ] 5.2 Implement bounded XML parsing and R4/profile validation with no DTDs, entities, remote resolution, or executable narrative rendering. Verify malformed/oversized/deep XML, unsupported extensions/resources, missing fields, wrong MIME type, and remote references fail at HTTP/integration boundaries without writes or network calls.
- [ ] 5.3 Implement exact patient DNI/birth-date matching, source-organization consistency, in-bundle references, and semantic record extraction. Verify independently authored Observation/MedicationRequest fixtures persist exact values, external authors/times/codings, and provenance while mismatched/ambiguous/multiple patients are rejected.
- [ ] 5.4 Implement atomic batch commit, same-file/request-key retries, clinical-record reuse across bundles, and conflicting source-identifier rejection. Verify concurrent duplicates, whitespace/reference-URN variants, mixed valid/invalid entries, changed retry payloads, and cross-patient ID reuse cannot produce partial or duplicate clinical data.
- [ ] 5.5 Add selected-record export and import/list/detail/original-file APIs with access checks and D4 limits. Verify selected records belong to the authorized patient, schema documents JSON versus XML outputs, and missing or inactive patients and unauthorized accounts cannot retrieve or write clinical data.
- [ ] 5.6 Add Interoperability navigation, admission export actions, selected-record export controls, file upload, import history, provenance detail, and original-file download. Verify B3/B4/B6 begin signed out at `/`, establish admission/import target state through UI, handle wrong-patient errors, and persist one result after retry.

## 6. Integration acceptance and delivery evidence

- [ ] 6.1 Complete OpenAPI examples and operator documentation for catalog ingestion, prescription reports, and the FHIR subset. Verify schema generation succeeds and every documented visible action/response corresponds to an implemented route and acceptance scenario.
- [ ] 6.2 Extend the isolated browser suite for B1-B6, including role-specific navigation, redirects, no-JavaScript forms, 20-row pagination, validation feedback, and persisted outcomes. Verify supported provisioning and fixture integrity; run the complete browser suite with zero skipped affected scenarios.
- [ ] 6.3 Extend disposable Compose acceptance seeding, browser journeys, and in-container persistence verification for B1-B6. Verify the workflow itself establishes target catalog entries, admissions, prescriptions, and imports and does not use seed shortcuts for the state under test.
- [ ] 6.4 Run Django checks, migration drift, Ruff format/check, mypy, and the appropriate full PostgreSQL regression suite; run independent FHIR conformance validation. Verify all configured checks pass and record failures or unavailable tooling as blockers rather than successful validation.
- [ ] 6.5 Run `uv run python .agents/skills/validate-live-app/scripts/validate_live_app.py` after extending both environments. Verify isolated and disposable Compose gates pass; report entry point/session, persona and initial state, visible actions, final URL/destination, persisted results, and executed/passed/skipped browser counts separately for each environment.
- [ ] 6.6 Verify the final diff stays within catalog management, prescribing, and FHIR exchange and run `openspec validate add-clinical-catalogs-prescriptions-fhir --strict`. Confirm existing registration behavior and shared clinical access remain regression-covered without new DNI, eligibility, or assignment requirements; keep related changes' tasks unchanged. Verify the final implementation summary explicitly defers license validity and makes no claim of full FHIR-server, regulatory, or running-development-app validation.
