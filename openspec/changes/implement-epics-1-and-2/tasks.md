Execution rules: this file is the implementation queue; the two specs define observable behavior and design.md D1-D10 define the selected contracts. Sections 1-4 are completed historical work and retain their original checkboxes. In particular, task 4.6 describes the pre-HU-04 auto-provisioning behavior; the new eligibility tasks deliberately supersede it. Do not undo completed patient/concurrency/pagination/production fixes.

Work sequentially from the first unchecked task. Each task ends after its stated verification; record results before checking it off. Read its D-section, named existing patterns, AGENTS.md, and applicable nested instructions first. Create the named new test files as part of that task; do not assume they already exist. Do not mark future work complete merely because planning artifacts validate.

API/HTML names and payloads come from D5-D7; do not invent parallel routes or custom error shapes. Keep normal refactor choices local, but record any discovered contract contradiction before implementing a divergent behavior. Do not broaden into appointments, account self-registration, or a full clinical chart.

Sections 5-8 form one releasable HU-04/HU-05 slice. Section 8.7's stricter eligibility must ship with completion/discovery, not alone. Sections 9-11 form HU-06; audited intervention routes ship only after audit/authorization are ready. Later sections depend on earlier sections unless a task states a narrower prerequisite. Commands use PostgreSQL; never substitute SQLite.

## 1. Shared Foundation

- [x] 1.1 Create a Python 3.13 `pyproject.toml` with Django 5.2 LTS, Django REST Framework 3.18, PostgreSQL driver, django-htmx, drf-spectacular, pytest-django, Playwright, Ruff, and mypy dependencies managed by `uv`; verify `uv lock` and `uv sync --frozen` succeed.
- [x] 1.2 Scaffold one Django project with `patients`, `professionals`, `clinical_records`, `access_control`, and `audit` apps using those exact app labels; verify `uv run python manage.py check` reports no issues and Django's app registry exposes all five labels.
- [x] 1.3 Add Docker Compose configuration for the Django application and PostgreSQL 18 with a database health check and example environment file; verify `docker compose config` succeeds and the application reaches the database.
- [x] 1.4 Configure Django exclusively against PostgreSQL for development and tests; verify migrations and a pytest database smoke test succeed without SQLite.
- [x] 1.5 Add a shared Django template shell with locally pinned HTMX and Bootstrap 5 assets; verify the rendered smoke page loads its styles and HTMX without external network requests.
- [x] 1.6 Configure Django session authentication, CSRF protection, administrative/professional groups, and default DRF permission behavior; verify anonymous unsafe requests fail and authenticated CSRF-valid requests succeed.
- [x] 1.7 Configure drf-spectacular and expose protected OpenAPI schema/documentation endpoints; verify schema generation succeeds without warnings.
- [x] 1.8 Configure pytest, pytest-django, PostgreSQL fixtures, factories, and a minimal Playwright browser smoke test; verify `uv run pytest` collects and passes all foundation tests.
- [x] 1.9 Configure Ruff, mypy, and pre-commit; verify formatting, linting, targeted type checks, and all hooks pass on the scaffold.
- [x] 1.10 Add GitHub Actions CI using a PostgreSQL service to run locked dependency installation, Django checks, migrations, tests, Ruff, and mypy; verify the workflow syntax is valid and its first run passes.
- [x] 1.11 Add shared DNI format validation that accepts only 7 or 8 ASCII digits without punctuation or whitespace; verify unit tests cover valid lengths, punctuation, whitespace, and invalid characters.
- [x] 1.12 Add role-aware actor context and shared authorization policies in `access_control` for administrative and medical-professional operations; verify protected-operation tests distinguish missing, administrative, and professional actors.
- [x] 1.13 Add specialty and hospital-service reference data with initial seed values; verify a clean Django migration exposes the seeded records.
- [x] 1.14 Document `uv` and Docker Compose setup, migration, test, quality-check, and seed commands; verify a fresh environment can follow the documented sequence successfully.

## 2. Sprint 1 - HU-01 Patient Registration and Maintenance

- [x] 2.1 Create the Django patient model and PostgreSQL constraints for internal ID, DNI, clinical record number, demographics, contact, address, insurer, and active status; verify the Django migration applies and rolls back on an empty database.
- [x] 2.2 Implement collision-safe clinical record number generation; verify repeated and concurrent generation tests produce unique values.
- [x] 2.3 Implement patient input validation for required values and field formats; verify unit tests cover every accepted and rejected field class.
- [x] 2.4 Implement transactional patient creation through a Django application service and DRF serializer with canonical-DNI uniqueness enforcement; verify service and API tests cover successful creation and duplicate rejection without partial writes.
- [x] 2.5 Build the administrative patient-registration Django template with HTMX submission; verify a valid submission displays the generated clinical record number and invalid fields show actionable messages.
- [x] 2.6 Implement patient detail retrieval for administrative users through DRF and the server-rendered view; verify the serializer contract contains all specified fields and excludes internal-only data.
- [x] 2.7 Implement patient demographic, contact, address, and insurer updates while protecting immutable identifiers; verify update tests prove ID and clinical record number cannot change.
- [x] 2.8 Implement confirmed patient deactivation and default exclusion of inactive patients; verify linked data remains present and inactive patients disappear from active-only results.

## 3. Sprint 1 - HU-02 Patient Search

- [x] 3.1 Add a unique index for canonical patient DNI; verify the database query plan uses the index for exact-DNI lookup.
- [x] 3.2 Implement an exact patient lookup service and DRF endpoint using canonical DNI; verify found and not-found API tests return the specified result shapes.
- [x] 3.3 Build the patient DNI search template with HTMX results showing full name and clinical record number; verify an administrative user can reach patient details with one action.
- [x] 3.4 Add the no-result registration action; verify a valid unmatched DNI can prefill a new patient registration without creating a record automatically.
- [x] 3.5 Measure patient lookup against a documented MVP-size dataset; verify the end-to-end p95 response time is below two seconds.
- [x] 3.6 Run the Sprint 1 HU-01/HU-02 acceptance walkthrough and record evidence; verify every scenario in the patient registration and search specs passes.

## 4. Sprint 2 - HU-03 Patient Admission

- [x] 4.1 Create admission and vital-sign persistence in `clinical_records` for patient, professional, consultation reason, blood pressure, heart rate, temperature, and server timestamp; verify Django migrations apply and PostgreSQL constraints reject orphaned patient or professional relations.
- [x] 4.2 Define configurable accepted ranges and units for all vital signs; verify boundary-value tests cover minimum, maximum, and out-of-range inputs.
- [x] 4.3 Implement admission creation for active patients and authenticated active medical professionals; verify authorization tests reject missing, inactive, or non-professional actors.
- [x] 4.4 Set admission timestamp and professional identity on the server; verify tests prove submitted overrides are ignored or rejected.
- [x] 4.5 Make admission creation atomic; verify invalid consultation reasons or vital signs create neither a complete nor partial admission record.
- [x] 4.6 Build the application login, medical workspace listing active patients, patient-DNI lookup, and admission Django templates with HTMX submission for consultation reason and all required vital-sign inputs; provision the minimal professional identity for active medical-role accounts that do not have one yet; redirect a staff medical professional without administrative permissions from the legacy Django Admin landing page into the clinical workspace; verify a non-staff professional reaches the workflow without Django Admin or an internal patient ID and error messages identify the specific missing or invalid value.
- [x] 4.7 Display the saved admission in the patient's record with professional and timestamp metadata; verify the visible data matches the persisted admission.
- [x] 4.8 Run the Sprint 2 HU-03 acceptance walkthrough and record evidence; verify every admission scenario in the patient-management spec passes.

## 5. HU-04 - Additive professional identity and upgrade

- [ ] 5.1 Implement the pure D3 license normalizer in professionals/license_validation.py and canonical validator in professionals/validators.py; reuse existing DNI/date validators. Verify professionals/test_validation.py covers surrounding whitespace, case, preserved hyphens/zeroes, Unicode, invalid lengths/characters, nonblank names, and future dates with `uv run pytest professionals/test_validation.py -q`.
- [ ] 5.2 Extend the existing Professional in professionals/models.py with D2 nullable fields and named PostgreSQL check/unique constraints; add a migration after current migrations. Verify professionals/test_professional_model.py covers incomplete rows, required completed fields, active-only DNI uniqueness, globally reserved licenses, and protected user/reference links; do not recreate IDs or edit old migrations.
- [ ] 5.3 Add sequence migration and professionals/identifiers.py generate_registration_number using the existing patients/identifiers.py pattern; allocate only at successful creation/completion. Verify professionals/test_identifiers.py tests format, repeated and dedicated-connection concurrent uniqueness, no number on invalid input, and preservation of an assigned number.
- [ ] 5.4 Add professionals/test_migrations.py with an old-schema active profile, inactive profile, User links, and a linked Admission. Apply new migrations and verify IDs, flags, FKs, row counts are unchanged and new personal/license fields are NULL; test empty-database reverse/forward without deleting historical data.
- [ ] 5.5 Add Professional completeness/display helpers needed by forms and lists without enabling stricter clinical access yet. Verify model tests distinguish incomplete active, incomplete inactive, complete active, and complete inactive profiles without inferring completeness from is_active alone.

## 6. HU-04 - Educational registry and durable verification outcomes

- [ ] 6.1 Add D3 LicenseRegistryEntry and LicenseVerification models/migrations in professionals; verification metadata is server-owned and verification rows have no normal update/delete API. Verify professionals/test_license_validation.py checks registry uniqueness/expiry fields, immutable verification rows, and no fabricated Professional for a failed check.
- [ ] 6.2 Register the educational registry for an explicitly authorized Django operator, verification records as read-only, and Professional as view-only in professionals/admin.py; label the source educational. Mark server-owned profile fields editable=False. Verify professionals/test_admin.py shows registry editing only with model permissions, prohibits verification edit/delete, and denies Professional add/change/delete even for a superuser; ordinary application users have no registry-management shortcut.
- [ ] 6.3 Implement the D3 provider protocol/local provider and LicenseResult in professionals/license_validation.py. Verify active, inclusive-expiry-day, expired, suspended, not_found, identity_mismatch, and injected unavailable outcomes in professionals/test_license_validation.py, with fixed test dates and no network calls.
- [ ] 6.4 Add verification orchestration that validates inputs/account before calling the provider and commits each performed result independently of profile mutation. Verify rejected/rolled-back registration leaves its verification history, invalid fields avoid unnecessary provider calls, clients cannot supply results, and over-60-second/expired results cannot activate a profile.

## 7. HU-04 - Professional services and concurrency

- [ ] 7.1 Implement D4 account resolution and shared administrative authorization in professionals/services.py; require a known active username without requiring an existing medical group. Verify professionals/test_services.py denies missing/wrong/inactive actors, rejects unknown/disabled subject accounts, and never creates passwords/accounts/staff privileges.
- [ ] 7.2 Implement register_professional for a new account using D2-D4, atomic profile+medical-group writes, server-owned number/verification fields, and database conflict handling. Verify service tests cover success, negative/unavailable license, inactive references, account/DNI/license conflict, and no partial group/profile writes.
- [ ] 7.3 Extend register_professional to complete an existing incomplete profile in place while preserving its active flag and admission links. Verify active/inactive legacy completion, missing fields, already-completed conflict, stable registration number, and rollback of failed completion in professionals/test_services.py.
- [ ] 7.4 Add a real PostgreSQL interleaving regression in professionals/test_concurrency.py for competing registrations/completions and DNI/license collisions after initial checks. Verify one identity/group result, field-specific conflict, no 500, and safe reference-state recheck; follow the dedicated-connection patient tests, not sleep-only assertions.
- [ ] 7.5 Implement update_professional with the D4 allowlist, current-state reload/lock, active-new-reference validation, and immutable identity rejection. Verify professionals/test_services.py covers each allowed field, identity/status injection, rejected incomplete profiles, inactive completed edits that preserve inactivity, replacement of retired references, retaining an unchanged retired reference during unrelated edits, and a stale active object after deactivation that cannot reactivate the current row.
- [ ] 7.6 Implement confirmed idempotent deactivate_professional and freshly verified reactivate_professional. Verify unchanged IDs, rejected unconfirmed/expired/suspended/unavailable/conflicting reactivation, preserved verification history, and refreshed return state; relationship cleanup is added in 9.5.
- [ ] 7.7 Implement the shared D4 eligibility predicate without wiring all entry points yet. Verify access_control/test_professional_eligibility.py covers active User/group/profile/completeness/license/date independently, expired active profiles, dual roles, and superuser-without-medical-role; no session-cached eligibility.

## 8. HU-04/HU-05 - API, discovery, and compatibility rollout

- [ ] 8.1 Add professional registration/detail/search serializers and API routes from D5, including inclusion in helixhealth/urls.py. Verify professionals/test_api.py asserts exact fields/statuses, read-only/unknown-key rejection, normalized license collisions, empty/found search envelopes, authorization before lookup, and no raw provider error leakage.
- [ ] 8.2 Add professional PATCH, deactivate, and reactivate API views using D4 services, session authentication, and CSRF. Verify API tests cover inactive/incomplete state, explicit confirmation, missing target, forbidden roles, conflicts, and successful persisted responses; PUT/DELETE stay 405.
- [ ] 8.3 Implement exact-DNI lookup, index queries, and 20-row active/inactive/incomplete index contexts in professionals/services.py and views.py. Verify professionals/test_search.py checks surrounding search whitespace, punctuation rejection, inactive exclusion, tab completeness rules, stable ordering, page boundaries, and index-backed lookup.
- [ ] 8.4 Add Professionals navigation, index/search/result/detail templates, and D5 routes. Verify professionals/test_views.py for least-privileged navigation, one-action detail access, prefilled unmatched registration, inactive/incomplete discovery, and correct actions for each state.
- [ ] 8.5 Add new/completion registration forms and templates with fixed username on completion, educational label, exact-username verification-history lookup, and bound errors. Verify field/409/503 feedback, HTMX 422/503 swapping, ordinary POST redirect, persisted IDs, and paginated history in professionals/test_views.py.
- [ ] 8.6 Add professional edit, deactivate, and reactivate forms/templates from D5, including Edit on inactive completed details to repair references before reactivation. Verify confirmation errors, preserved identifiers/activation state, failed fresh verification, and visible active/inactive/expired states; explain that an expired active profile is deactivated then explicitly reactivated for a new verification.
- [ ] 8.7 After 8.4-8.6, wire the shared eligibility predicate through login/home redirects, context processors, legacy middleware, HU-03 services/UI/API, and medical navigation. Remove active auto-provisioning on login. Verify existing authentication/admission regressions plus access_control/test_professional_eligibility.py; update missing-profile expected behavior explicitly and preserve staff administrative access.
- [ ] 8.8 Add B1/B2/B3 isolated browser journeys to tests/test_browser_workflows.py: non-staff admin starts at /, registers an account without profile/medical role, completes an old identity, and sees failed verification feedback; a fresh medical login proves eligibility. Verify persisted identity/group/admission links and that inactive completion stays inactive; do not seed the state being established.
- [ ] 8.9 Add B4/B8 professional maintenance/search/pagination browser journeys, including invalid edits, confirmation, denied expired/DNI-conflicting reactivation, 21-record pages, and return to saved detail. Verify `uv run pytest -m browser -q` executes these with no skipped cases.
- [ ] 8.10 Extend seed_acceptance, verify_acceptance, and run_compose_acceptance.py for B1-B4/B8 using synthetic registry inputs and supported registration for unrelated background professionals. Replace the old missing-profile auto-activation expectation with denied-then-administrator-completed behavior. Verify the disposable live validator passes and preserves old admission and patient journeys.
- [ ] 8.11 Document HU-04 upgrade/registration/reactivation operator steps in docs/acceptance/sprint-3-hu-04-hu-05.md, including existing inactive and no-role account cases. Verify every documented action corresponds to a visible control exercised by 8.8-8.10; never claim incomplete legacy data was backfilled automatically.

## 9. HU-06 - Care relationship lifecycle

- [ ] 9.1 Add D6 CareRelationship model/migration with protected links, assignment/revocation metadata, and unique active pair. Verify clinical_records/test_care_relationships.py covers duplicate/orphan constraints, revoke consistency, and history-preserving reassignment.
- [ ] 9.2 Implement assign_care_relationship and revoke_care_relationship in clinical_records/care_services.py using D6 lock order and current eligibility. Verify idempotent duplicate assignment, explicit revoke confirmation, inactive/ineligible endpoints, wrong actor, and wrong-patient relationship rejection.
- [ ] 9.3 Add D6 administrative care-team API/HTML routes via patients/urls.py and clinical_records/care_views.py. Verify clinical_records/test_care_views.py checks payload/status contracts, bounded assignment list, authorization, CSRF, and no disclosure of intervention notes under administrative privileges.
- [ ] 9.4 Add Care team link to administrative patient detail and assignment/revocation templates using known professional DNI. Verify B5 browser journey begins without the relationship, assigns via visible lookup, confirms revoke, and persists actor/time/history; repeated submit must not add another active row.
- [ ] 9.5 Integrate relationship termination into existing patient deactivation and professional deactivation, preserving D6 lock order. Verify service/HTTP tests preserve admissions/notes/audits, revoke active relationships, and leave them revoked after professional reactivation.
- [ ] 9.6 Add clinical_records/test_care_concurrency.py for assignment versus endpoint deactivation and duplicate assignments on separate PostgreSQL connections. Verify no active assignment is committed after an earlier deactivation wins, no deadlock from reversed lock order, and no duplicate pair.
- [ ] 9.7 Extend disposable Compose B5 coverage and persistence verifier to establish/revoke the relationship through the UI, not a seed shortcut. Verify the full validator passes before enabling the next clinical surface.

## 10. HU-06 - Intervention and audit storage boundary

- [ ] 10.1 Add D7 Intervention model/migration with immutable note metadata, protected relations, unique same-chain successor, and original/correction validation. Verify clinical_records/test_interventions.py covers length/blank bounds, protected history, preserved originals, correct patient linkage, rejected model/QuerySet update/delete, and absence from Django Admin; do not expose routes yet.
- [ ] 10.2 Add D8 AuditEvent schema/migration with nullable verified identity, requested target IDs, allowed enums, result reference, and content-free metadata. Verify audit/tests.py can represent anonymous/unknown-target attempts without fabricated FKs and rejects invalid shapes.
- [ ] 10.3 Add PostgreSQL audit UPDATE/DELETE rejection triggers and read-only audit Admin. Verify audit/test_integrity.py rejects model save updates, ORM bulk update/delete, and ordinary SQL mutation while preserving rows; explicitly authorized Admin may inspect only.
- [ ] 10.4 Implement D8 audited-operation orchestration in audit/services.py with authorization inside the boundary, evaluated results, savepoints, one event per dispatched request, and expected errors returned only after denial audit commits. Verify audit/test_operations.py covers allowed read, denial, validation error, conflict, and redirect-followed read semantics.
- [ ] 10.5 Add audit-storage-failure integration tests at the service/HTTP boundary. Verify a failed audit insert produces generic 503, rolls back note/correction writes, returns no clinical data, and emits only content-free operational logging; do not swallow or falsely report a persisted audit.
- [ ] 10.6 Verify migrations forward/backward on an empty disposable database and forward with prior patients/professionals/admissions. Verify existing rows are unchanged and audit-trigger removal exists only in the controlled schema reverse, never an application operation.

## 11. HU-06 - Audited clinical interface

- [ ] 11.1 Implement list_interventions and view_intervention (correction-form GET) authorization in clinical_records/intervention_services.py through D8. Verify clinical_records/test_intervention_access.py separately denies inactive account, missing role/profile, incomplete/expired profile, inactive patient, unlinked/nonexistent patient; generic 403 and correct audit references must hold before querying note contents, with one list/view event for the corresponding permitted read.
- [ ] 11.2 Implement create_intervention within the audited boundary; validate application fields inside that boundary so dispatched invalid input is audited. Verify note length/escaping input, server-owned metadata, injected fields, allowed audit, and rollback in clinical_records/test_interventions.py.
- [ ] 11.3 Implement correct_intervention with D7 current-chain rules and D6 lock order. Verify original preservation, same-patient target, current assignment, required reason, new author/time, and original/result audit linkage in clinical_records/test_interventions.py.
- [ ] 11.4 Add D7 intervention JSON routes/serializers and permission arrangement. Verify clinical_records/test_intervention_api.py checks anonymous reads are audited before 403, CSRF remains enforced, list/create/correct payload/status contracts, 20-row pagination, cross-patient 404, 405 for in-place modification, and no unaudited generic CRUD path.
- [ ] 11.5 Add My patients UI and navigation using active assigned patients only. Verify clinical_records/test_intervention_views.py covers eligibility, stable 20-row pages, no unrelated patient links, and no content disclosure through administrative role alone.
- [ ] 11.6 Add intervention list/create/correct templates/forms and explicit 422/503 feedback; escape text, label originals/corrections, and keep return links. Verify HTML tests cover empty/found history, invalid inputs, correction-form read auditing, redirects, and pagination.
- [ ] 11.7 Add B6 isolated browser journey: after B5 assignment through supported workflow, a fresh non-staff professional login follows My patients, sees empty history, creates a note, and corrects it. Verify original/correction rows, author/time, and exact audit actions/outcomes; no fixture may directly create the target note.
- [ ] 11.8 Add B7/B8 browser journeys for UI revocation, refreshed clinical access denial, old bookmarked URL denial, inactive/expired profile, unrelated professional, and 21-note history pagination. Verify both discoverability and preserved history; direct URLs are only negative/bookmark regression probes.
- [ ] 11.9 Add clinical_records/test_intervention_concurrency.py for correction-vs-correction and note/read-vs-revocation/deactivation using independent PostgreSQL connections. Verify one correction successor, persisted loser conflict audit, and no data/mutation after revocation wins.
- [ ] 11.10 Extend production Compose journeys and persistence verification for B5-B8, plus a permitted audit operator inspecting events in read-only Admin. Verify sign-out between roles, no fixture bypass of target state, correct note/correction/audit relations, denied access, and cleanup of only disposable resources.

## 12. Epic completion and evidence

- [ ] 12.1 Add HU-05 performance and query-plan coverage in professionals/test_search.py per D10: 10,000 synthetic completed records, 40 authenticated requests, nearest-rank p95 <2 seconds. Verify both found and empty contracts and record environment/timing in docs/acceptance/sprint-3-hu-04-hu-05.md; bulk background fixtures do not claim to test registration.
- [ ] 12.2 Inspect production access logging and application error logging for sensitive query/payload leakage; exclude raw lookup query strings and note/verification content. Add tests capturing routine logs and error responses with known synthetic DNI/license/note values and verify those values are absent; retain useful method/path/status/correlation information.
- [ ] 12.3 Add docs/acceptance/sprint-4-hu-06.md with B5-B9 evidence and a traceability matrix mapping every requirement/scenario in both specs to tests and visible demonstration steps. Verify every scenario has a concrete test/step or an explicit unresolved blocker; no blank mappings or acceptance by fixture-only state.
- [ ] 12.4 Update README/operator documentation for account provisioning, educational registry setup, legacy completion, role-specific entry paths, professional lifecycle, care assignment, and intervention corrections. Verify documented examples match exact routes/labels and migration order; preserve the existing production/static/proxy setup.
- [ ] 12.5 Run locked dependency sync, Django system checks, migration drift check, Ruff format/check, and mypy using the command block below. Resolve failures; verify no unintended dependency upgrade, rewritten historical migration, or weakened authorization test.
- [ ] 12.6 Run the full suite against disposable PostgreSQL, including migration, concurrency, API, audit, performance, and browser tests. Verify zero failures/skipped browser journeys and record actual counts; historical 166/10 counts are not completion criteria.
- [ ] 12.7 Run the bundled live validator after all runtime changes. Verify the current production-mode Compose image passes secure deployment/static/host checks, every affected role journey from a fresh signed-out entry, and persisted verification; record isolated-browser counts separately from Compose journey counts and preserve evidence.
- [ ] 12.8 Reconcile tasks/specs/design with delivered behavior and completed evidence. Verify original HU-01/HU-02/HU-03 scenarios still pass except the explicitly specified HU-04 eligibility transition; report unfinished work honestly. Do not archive or claim Epics complete while a required scenario is skipped or blocked.

Verification command block (run from repository root; follow README and the live-validation skill for disposable PostgreSQL rather than resetting user data):

    uv sync --frozen
    uv run python manage.py check
    uv run python manage.py makemigrations --check --dry-run
    uv run ruff format --check .
    uv run ruff check .
    uv run mypy
    uv run pytest
    uv run python .agents/skills/validate-live-app/scripts/validate_live_app.py

The full pytest command needs a reachable disposable PostgreSQL database configured through DB_* variables. The live validator creates its own distinct isolated/Compose environments. Report which environment each result describes. Unavailable browsers/services are blockers to validation, not permission to substitute SQLite or mark browser tests skipped as done.
