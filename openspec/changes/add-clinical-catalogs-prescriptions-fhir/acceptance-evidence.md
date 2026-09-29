# Acceptance evidence — 2026-09-29

## Changes

The isolated suite and disposable Compose journeys share catalog upload steps:
21 entries are created through the visible JSON form, an exact retry reports
21 unchanged entries, conflicting and invalid uploads are rejected atomically,
and search/pagination shows exactly 20 entries followed by one entry. Rejected
rows remain absent from both the visible search and persistence checks.

Both environments exercise ordinary forms without JavaScript for catalog,
prescription, and exchange workflows. Prescription resubmission returns to the
same issued prescription; Compose now issues two items. Downloaded prescription
and admission XML is parsed by the independent R4 resource model and official
local schema. Original import downloads must match the uploaded bytes.

The isolated doctor prerequisite uses the supported professional registration
service. Seed-integrity regression assertions require target catalogs,
prescriptions, imports, and the target admission to be absent; unrelated legacy
history remains background data. Compose persistence verification checks upload
counts, rejected-row absence, one prescription with two items, one import and
external record, external author/coding/source, and the target admission count.

## Checks

- Django system checks: passed.
- All migrations applied to a fresh disposable PostgreSQL 18 database.
- Migration drift (`makemigrations --check --dry-run`): none.
- Ruff check and format check: passed on configured tracked Python sources plus
  the new helper, using `--force-exclude --no-cache` to honor project exclusions
  and avoid inaccessible temporary directories. Directory-wide traversal hit
  local ACL errors and a Ruff crash; explicit source checks succeeded.
- mypy: passed, 90 source files.
- Full non-browser PostgreSQL regression: 294 passed, 0 skipped; 27 browser tests
  deselected for the separate browser gate.
- Independent conformance is included in that regression: official local R4 XSD,
  pinned independent `fhir.resources` model, and application profile validation
  accept independent valid fixtures and reject invalid types, codes, units,
  references, malformed XML, and external entities without remote resolution.
- OpenSpec strict validation: passed.

## Browser environments

The complete isolated browser gate passed: 27 executed, 27 passed, 0 skipped.
It uses Django's isolated live server and a fresh PostgreSQL test database.
Disposable Compose validation is being repeated after correcting a browser
selector: the no-JavaScript name-search form must submit with “Search names,”
not the separate DNI form's “Find patient” button.

Every affected journey begins signed out at `/` and signs in through visible
product navigation. The administrative persona is non-staff, non-superuser, with
the application administrative role. The medical persona has the medical role
and an active professional profile provisioned through supported registration.
The selected patient is active; the target prescription and import do not exist.

| Journey | Visible actions and final destination | Persisted/observable result |
| --- | --- | --- |
| B1 | Catalogs; create/edit/delete specialty; add terminology and medication; import/retry/reject JSON; search and paginate. Ends on `/catalogs/medications/?search=REJECTED-UPLOAD`. | Deleted unused specialty; one terminology; one manual medication plus 21 uploaded medications; no rejected row. |
| B2 | Clinical workspace; patient admission page; Prescriptions; invalid then valid two-item issue; browser-back resubmit; report and XML. Ends on `/clinical-records/patients/<id>/prescriptions/<uuid>/`. | Exactly one prescription and two items; same detail URL on retry; printable report and schema/model-valid downloaded XML. |
| B3 | Record admission through visible form; Interoperability; select admission; export XML. Ends on the patient's interoperability page. | One target admission with entered vitals; downloaded R4 XML; three Observations in isolated verification. |
| B4 | Interoperability; upload independent matching fixture; inspect detail; download original; retry import. Ends on the import detail. | One import batch and one external record; byte-exact original download; external author/source/coding retained; no fabricated local prescription or admission. |
| B5 | Sign in as active medical, missing-profile and inactive personas; inspect role-specific navigation and redirects. | Existing clinical eligibility is preserved; denied personas remain at `/`; medical navigation hides Catalogs. HTTP regressions cover retrieval access and CSRF boundaries. |
| B6 | Interoperability; upload wrong-patient fixture; read inline feedback; correct/retry through the form. | Useful identity-mismatch error and no partial import; backend regression covers malformed/unsafe XML. |

## Scope

License validity remains deferred. These checks cover the documented local FHIR
R4 subset; they do not establish full FHIR-server or regulatory conformance.
Disposable Compose validation is distinct from validation of a running
development application. Related changes' task lists are unchanged.
