## 1. Shared Foundation

- [x] 1.1 Create a Python 3.13 `pyproject.toml` with Django 5.2 LTS, Django REST Framework 3.18, PostgreSQL driver, django-htmx, drf-spectacular, pytest-django, Playwright, Ruff, and mypy dependencies managed by `uv`; verify `uv lock` and `uv sync --frozen` succeed.
- [x] 1.2 Scaffold one Django project with `patients`, `professionals`, `clinical_records`, `access_control`, and `audit` apps using those exact app labels; verify `uv run python manage.py check` reports no issues and Django's app registry exposes all five labels.
- [x] 1.3 Add Docker Compose configuration for the Django application and PostgreSQL 18 with a database health check and example environment file; verify `docker compose config` succeeds and the application reaches the database.
- [x] 1.4 Configure Django exclusively against PostgreSQL for development and tests; verify migrations and a pytest database smoke test succeed without SQLite.
- [x] 1.5 Add a shared Django template shell with locally pinned HTMX and Bootstrap 5 assets; verify the rendered smoke page loads its styles and HTMX without external network requests.
- [x] 1.6 Configure Django session authentication, CSRF protection, administrative/professional groups, and default DRF permission behavior; verify anonymous unsafe requests fail and authenticated CSRF-valid requests succeed.
- [x] 1.7 Configure drf-spectacular and expose protected OpenAPI schema/documentation endpoints; verify schema generation succeeds without warnings.
- [ ] 1.8 Configure pytest, pytest-django, PostgreSQL fixtures, factories, and a minimal Playwright browser smoke test; verify `uv run pytest` collects and passes all foundation tests.
- [ ] 1.9 Configure Ruff, mypy, and pre-commit; verify formatting, linting, targeted type checks, and all hooks pass on the scaffold.
- [ ] 1.10 Add GitHub Actions CI using a PostgreSQL service to run locked dependency installation, Django checks, migrations, tests, Ruff, and mypy; verify the workflow syntax is valid and its first run passes.
- [ ] 1.11 Add shared DNI normalization and format validation; verify unit tests cover punctuation, whitespace, invalid characters, and equivalent normalized values.
- [ ] 1.12 Add role-aware actor context and shared authorization policies in `access_control` for administrative and medical-professional operations; verify protected-operation tests distinguish missing, administrative, and professional actors.
- [ ] 1.13 Add specialty and hospital-service reference data with initial seed values; verify a clean Django migration exposes the seeded records.
- [ ] 1.14 Document `uv` and Docker Compose setup, migration, test, quality-check, and seed commands; verify a fresh environment can follow the documented sequence successfully.

## 2. Sprint 1 - HU-01 Patient Registration and Maintenance

- [ ] 2.1 Create the Django patient model and PostgreSQL constraints for internal ID, DNI, clinical record number, demographics, contact, address, insurer, and active status; verify the Django migration applies and rolls back on an empty database.
- [ ] 2.2 Implement collision-safe clinical record number generation; verify repeated and concurrent generation tests produce unique values.
- [ ] 2.3 Implement patient input validation for required values and field formats; verify unit tests cover every accepted and rejected field class.
- [ ] 2.4 Implement transactional patient creation through a Django application service and DRF serializer with normalized-DNI uniqueness enforcement; verify service and API tests cover successful creation and duplicate rejection without partial writes.
- [ ] 2.5 Build the administrative patient-registration Django template with HTMX submission; verify a valid submission displays the generated clinical record number and invalid fields show actionable messages.
- [ ] 2.6 Implement patient detail retrieval for administrative users through DRF and the server-rendered view; verify the serializer contract contains all specified fields and excludes internal-only data.
- [ ] 2.7 Implement patient demographic, contact, address, and insurer updates while protecting immutable identifiers; verify update tests prove ID and clinical record number cannot change.
- [ ] 2.8 Implement confirmed patient deactivation and default exclusion of inactive patients; verify linked data remains present and inactive patients disappear from active-only results.

## 3. Sprint 1 - HU-02 Patient Search

- [ ] 3.1 Add a unique index for normalized patient DNI; verify the database query plan uses the index for exact-DNI lookup.
- [ ] 3.2 Implement an exact patient lookup service and DRF endpoint using normalized DNI; verify found and not-found API tests return the specified result shapes.
- [ ] 3.3 Build the patient DNI search template with HTMX results showing full name and clinical record number; verify an administrative user can reach patient details with one action.
- [ ] 3.4 Add the no-result registration action; verify a valid unmatched DNI can prefill a new patient registration without creating a record automatically.
- [ ] 3.5 Measure patient lookup against a documented MVP-size dataset; verify the end-to-end p95 response time is below two seconds.
- [ ] 3.6 Run the Sprint 1 HU-01/HU-02 acceptance walkthrough and record evidence; verify every scenario in the patient registration and search specs passes.

## 4. Sprint 2 - HU-03 Patient Admission

- [ ] 4.1 Create admission and vital-sign persistence in `clinical_records` for patient, professional, consultation reason, blood pressure, heart rate, temperature, and server timestamp; verify Django migrations apply and PostgreSQL constraints reject orphaned patient or professional relations.
- [ ] 4.2 Define configurable accepted ranges and units for all vital signs; verify boundary-value tests cover minimum, maximum, and out-of-range inputs.
- [ ] 4.3 Implement admission creation for active patients and authenticated active medical professionals; verify authorization tests reject missing, inactive, or non-professional actors.
- [ ] 4.4 Set admission timestamp and professional identity on the server; verify tests prove submitted overrides are ignored or rejected.
- [ ] 4.5 Make admission creation atomic; verify invalid consultation reasons or vital signs create neither a complete nor partial admission record.
- [ ] 4.6 Build the medical admission Django template with HTMX submission for consultation reason and all required vital-sign inputs; verify error messages identify the specific missing or invalid value.
- [ ] 4.7 Display the saved admission in the patient's record with professional and timestamp metadata; verify the visible data matches the persisted admission.
- [ ] 4.8 Run the Sprint 2 HU-03 acceptance walkthrough and record evidence; verify every admission scenario in the patient-management spec passes.

## 5. Sprint 3 - HU-04 Professional Registration and Maintenance

- [ ] 5.1 Create the Django professional model and PostgreSQL constraints for internal ID, DNI, license, registration number, personal data, specialty, service, license status, and active status; verify the Django migration applies and rolls back cleanly.
- [ ] 5.2 Implement collision-safe professional registration number generation; verify repeated and concurrent generation tests produce unique values.
- [ ] 5.3 Define the license-status provider contract and a controlled local MVP registry; verify provider tests return active, non-active, and unavailable outcomes.
- [ ] 5.4 Implement professional input validation for required values, specialty, and service assignment; verify unit tests cover every accepted and rejected field class.
- [ ] 5.5 Implement transactional professional creation through a Django application service and DRF serializer with normalized DNI, unique license, and fail-closed license validation; verify successful, duplicate, expired, suspended, and unavailable-license tests.
- [ ] 5.6 Build the administrative professional-registration Django template with HTMX submission; verify a valid submission displays the generated registration number and invalid fields show actionable messages.
- [ ] 5.7 Implement professional detail retrieval and editing while protecting immutable identifiers; verify update tests prove internal ID and registration number cannot change.
- [ ] 5.8 Implement specialty and hospital-service reassignment; verify only configured active reference values can be assigned.
- [ ] 5.9 Implement confirmed professional deactivation and reactivation with fresh license validation; verify deactivation blocks clinical access and reactivation fails for a non-active license.

## 6. Sprint 3 - HU-05 Professional Search

- [ ] 6.1 Add unique indexes for normalized professional DNI and license number; verify database query plans use the expected index for exact lookup.
- [ ] 6.2 Implement an exact professional lookup service and DRF endpoint using normalized DNI; verify found and not-found API tests return the specified result shapes.
- [ ] 6.3 Build the professional DNI search template with HTMX results showing full name and license number; verify an administrative user can reach professional details with one action.
- [ ] 6.4 Add the no-result registration action; verify a valid unmatched DNI can prefill professional registration without creating a record automatically.
- [ ] 6.5 Measure professional lookup against a documented MVP-size dataset; verify the end-to-end p95 response time is below two seconds.
- [ ] 6.6 Run the Sprint 3 HU-04/HU-05 acceptance walkthrough and record evidence; verify every professional registration and search scenario passes.

## 7. Sprint 4 - HU-06 Professional Intervention Access

- [ ] 7.1 Create the `clinical_records` care-relationship model linking active professionals and patients; verify PostgreSQL constraints prevent orphaned and duplicate active relationships.
- [ ] 7.2 Add the minimal `clinical_records` intervention read model and DRF serializer needed to list a patient's recorded interventions; verify tests distinguish patients with no interventions from inaccessible patients.
- [ ] 7.3 Implement authorization requiring authenticated identity, active professional status, and a care relationship; verify each missing condition independently denies access.
- [ ] 7.4 Implement the professional's patient-intervention query; verify an authorized professional sees only interventions for the requested linked patient.
- [ ] 7.5 Build the professional intervention-access Django template and HTMX results view; verify successful, empty, and denied states disclose only appropriate information.
- [ ] 7.6 Create the append-only `audit` app model for timestamp, professional, patient, action, target, and outcome; verify normal application operations and DRF endpoints cannot update or delete an audit event.
- [ ] 7.7 Audit every successful and denied intervention consultation; verify one complete audit event is created for each tested access attempt.
- [ ] 7.8 Audit every permitted intervention modification path available in the MVP; verify the event identifies actor, patient, target, action, outcome, and server time.
- [ ] 7.9 Verify deactivated professionals lose intervention access immediately; verify the denied attempt is recorded without exposing patient data.
- [ ] 7.10 Run the Sprint 4 HU-06 acceptance walkthrough and record evidence; verify every authorization and audit scenario in the professional-management spec passes.

## 8. Epic 1 and Epic 2 Completion

- [ ] 8.1 Run `uv sync --frozen`, Django checks and migrations, `uv run pytest`, Ruff, and mypy against a clean PostgreSQL database; verify all unit, integration, browser, authorization, audit, migration, and performance checks pass.
- [ ] 8.2 Review user-facing errors and logs for sensitive data exposure; verify DNI, contact, vital signs, and intervention data are absent from unauthorized responses and routine logs.
- [ ] 8.3 Produce a traceability matrix mapping HU-01 through HU-06 and every acceptance criterion to tests and demonstration steps; verify no criterion is unmapped.
- [ ] 8.4 Update operator and user documentation for patient, admission, professional, and intervention workflows; verify each documented workflow can be completed in a fresh seeded environment.
- [ ] 8.5 Demonstrate the four sprint objectives in order and capture results; verify Epics 1 and 2 meet their detailed acceptance criteria without relying on Epic 3 appointment functionality.
