## Context

See proposal.md for purpose. This is an extension of a working application. HU-01/HU-02 and HU-03 are implemented. The reviewed baseline had 166 passing tests (10 isolated Chromium tests) and 8 passing disposable production-Compose journeys; those counts are historical, not a fixed future target.

Read the applicable rows before implementing a task:

| Concern | Existing source / pattern |
|---|---|
| Patient identity, validation, sequence | patients/models.py, identifiers.py, validators.py |
| Transactional writes, duplicate conflicts | patients/services.py, test_services_api.py |
| Forms, API, navigation | patients/forms.py, serializers.py, views.py, urls.py; templates/patients/ |
| Admissions and concurrency regression | clinical_records/models.py, services.py, test_admissions.py |
| Existing professional identity | professionals/models.py; migrations through 0003_professional_admission_identity.py |
| Roles and clinical eligibility | access_control/actors.py, policies.py, medical_professionals.py |
| Login/navigation integration | access_control/views.py, middleware.py, context_processors.py; helixhealth/views.py |
| Pagination | templates/_pagination.html and patient/clinical views (20 rows) |
| Acceptance | tests/test_browser_workflows.py; .agents/skills/validate-live-app/scripts/; access_control/management/commands/seed_acceptance.py and verify_acceptance.py |
| Operations | README.md, pyproject.toml, compose.yaml, compose.production.yaml, docker-entrypoint.sh, helixhealth/settings.py |

Professional already has an immutable id, protected one-to-one user, and is_active. Admissions reference that row. Login currently can create a minimal active profile. D2/D4 replace that activation behavior at HU-04 rollout. Do not replace the Professional table, rewrite old migrations, or recreate user/admission identities.

## Goals / Non-Goals

**Goals:** decide missing contracts before implementation, preserve clinical history, make workflows discoverable, and enforce authorization/auditing for both HTML and API consumers.

**Non-Goals:** stack changes, account self-registration, external registry integration, a full clinical chart, and admission amendments. The only new clinical authoring surface is a plain-text intervention note with a preserved correction.

## Decisions

### D1. Preserve the architecture and completed invariants

Keep Python 3.13, Django 5.2 LTS, DRF, PostgreSQL 18, HTMX/Bootstrap, and uv.lock. No new runtime package is required for the remaining domain work. professionals owns professional/registry/verification data; clinical_records owns care relationships and interventions; access_control owns shared policies; audit owns immutable events. Put rules in services used by both forms and API serializers. A second implementation in views is prohibited.

Preserve conditional active-patient DNI uniqueness, immutable patient identifiers, row-locked patient updates/deactivation/admission, conflict handling outside rolled-back savepoints, immutable admissions, and bounded lists/history. Do not restore full-table rendering to satisfy the phrase "all active patients." Do not make database uniqueness prechecks the sole protection against duplicates.

### D2. Extend Professional in place

Add nullable fields for legacy profiles. Use NULL, not empty strings, for missing unique values. Completion supplies every required value in one transaction.

| Field | Contract |
|---|---|
| id, user | Preserve values and user one-to-one/PROTECT. Immutable. |
| dni | Nullable CharField(8), canonical 7/8 ASCII digits. Partial unique constraint when is_active=True and dni is non-null. Immutable after completion. |
| registration_number | Nullable unique CharField(32), PostgreSQL sequence format PR-00000001. Minimum width 8 digits; gaps allowed. Immutable once assigned. |
| first_name, last_name | Nullable CharField(150); completion/update requires trimmed nonblank text. Store on Professional; do not overwrite account names. |
| date_of_birth | Nullable DateField, required at completion, not in future; reuse patient validator. |
| license_number | Nullable globally unique CharField(32), D3 canonicalization; reserved even when inactive. Immutable after completion. |
| specialty, hospital_service | Nullable protected FKs to existing reference models. Only active values can be newly assigned. |
| license_status | unverified initially; successful verification stores active. No client may set it. |
| license_verified_at, license_valid_until | Nullable server datetime and DateField, set on successful registration/reactivation. |
| registration_completed_at | Nullable immutable server datetime; non-null indicates successful complete registration. |
| is_active | Preserve existing flag during migration AND completion; a newly created verified profile starts active. Reactivation is explicit. |

Database checks enforce canonical non-null DNI/license, nonempty generated number, and complete required fields/verification metadata when registration_completed_at is non-null. A complete inactive row retains its data. Application validation additionally checks nonblank values, dates, and active references.

Use sequence allocation at save/completion, never count()+1 or max()+1. Do not backfill fabricated DNI/licenses/names/numbers. An inactive DNI may be reused by another professional with a different license; reactivating the original must fail if its DNI is now held by another active row.

### D3. Educational license provider and verification history

Create professionals/license_validation.py with normalize_license(value) and a provider protocol verify(*, license_number, dni) -> LicenseResult.

Normalization: strip surrounding whitespace, uppercase, then require ASCII regex ^[A-Z0-9][A-Z0-9-]{2,31}$. Preserve hyphens and leading zeroes. Examples: " mn-001234 " becomes "MN-001234"; "MN001234" remains a different identifier; internal spaces, dots, slashes, Unicode lookalikes, and fewer than 3 characters are invalid. This is a controlled MVP identifier format, not a rule for every real licensure jurisdiction.

LicenseResult contains status, checked_at (server timestamp), valid_until (nullable date on failure), and source="local-mvp". Status: active, expired, suspended, not_found, identity_mismatch, or unavailable.

LicenseRegistryEntry stores unique canonical license_number, canonical dni, status (active/expired/suspended), and required valid_until. The local provider returns not_found for no entry; identity_mismatch for wrong DNI; otherwise expired if valid_until precedes the current application date; otherwise the stored status. The expiry date is inclusive. Operational provider errors map to unavailable. Unknown entries never default to active. Test unavailable with an injected fake provider; no external calls, retries, periodic refresh, or new infrastructure.

Only an authorized Django Admin operator with the registry model permissions manages registry entries. Ordinary application administrators cannot edit the registry. Acceptance fixtures may seed synthetic registry entries as background prerequisites; the professional registration itself must use the supported workflow.

LicenseVerification records every provider invocation: immutable id, actor User/PROTECT, subject User/PROTECT, canonical attempted DNI/license, status, checked_at, valid_until, source. Save this independently before the professional mutation transaction so negative outcomes survive. It is a verification record, not a pending/created Professional. Incomplete-profile or registration screens show the subject account's verification history to administrators only, 20 entries per page, after exact username lookup. For a username with no profile, render history on the registration page; for an existing profile, show it on detail/completion. Protect model/admin from normal update/delete and expose no write API.

Validate fields, account existence, and obvious duplicates before invoking the provider. A result can be used only by that service call for that exact account/DNI/license, while no more than 60 seconds old and not expired. Never accept a client-supplied result. A successful profile stores the verification snapshot: future registry edits do not silently change it. Stored date expiry and explicit deactivation still revoke eligibility on the next request. Clearly label this educational limitation in UI/docs. No raw exceptions or DNI/license values in routine logs.

### D4. Professional lifecycle and the legacy-access transition

A Django administrator creates an active login account through Django Admin. The application administrator knows its username and registers its professional data through the product UI. Do not create passwords, second accounts, or staff privileges. Bind by exact username only. Successful registration adds the Medical Professionals group; membership is not a prerequisite. Registration for an already completed account returns conflict.

Make Professional Admin view-only, with add/change/delete disabled even for a superuser. All professional lifecycle writes use the product services below; account provisioning and registry administration remain separate supported operator workflows. Mark generated numbers, verification snapshots, and completion timestamps editable=False so generated forms cannot make them client-owned.

Use keyword-only services in professionals/services.py:

| Service | Inputs / result |
|---|---|
| register_professional | actor, username, dni, first_name, last_name, date_of_birth, license_number, specialty_code, hospital_service_code; returns new or completed Professional |
| update_professional | actor, professional, changes; allow only names, birth date, specialty_code, hospital_service_code on completed profiles, active or inactive; preserve is_active |
| deactivate_professional | actor, professional, confirmed; explicit true, idempotent; end its active care relationships once D6 exists; return refreshed state |
| reactivate_professional | actor, professional, confirmed; completed inactive profile, fresh verification, active references, no active DNI conflict; return refreshed state |
| lookup_professional_by_dni | actor, canonical dni; return active completed match or None |

Completion updates an existing incomplete row without changing its id/user or active flag. An inactive completed row displays "Registration complete; profile remains inactive" and requires a separate Reactivate action. Invalid registration never creates a profile or changes group membership; existing profiles stay unchanged. Performed license checks remain in verification history.

An expired but active profile is visibly ineligible. Its renewal path is confirmed deactivation followed by confirmed reactivation with fresh verification. Explain both steps on detail; no hidden license refresh or alternate edit path is permitted.

An inactive completed profile may be edited without activating it, so an administrator can replace an inactive specialty/service before reactivation. Validate that newly selected references are active; retaining an unchanged inactive reference is allowed during an unrelated edit, but reactivation requires both references active.

Write algorithm: authorize against current active User/group state; validate inputs; invoke/persist D3 verification where needed; enter transaction.atomic; lock subject User then existing Professional and selected reference rows; recheck state and result freshness; allocate number if absent; write profile and group; commit. Catch identified DNI/license/account uniqueness conflicts outside an inner savepoint and map to 409. Unrelated validation stays 400; unexpected errors are not mislabeled as duplicates. Do not hold locks while calling the provider.

Central eligibility in access_control/medical_professionals.py requires active User, medical group, active Professional, completed registration, stored active license, and license_valid_until on/after today. Read fresh state each request. Apply it to login/home redirects, navigation context, legacy middleware, HU-03 HTML/API/services, and HU-06. A superuser without the medical group has no implicit clinical role.

Incomplete/inactive/expired profiles can authenticate but reach / with "Professional registration or reactivation is required. Contact an administrator." No clinical navigation; direct clinical requests return 403. A disabled User cannot authenticate. A dual-role user with ineligible professional profile retains administrative access and its administrative landing page.

At HU-04 rollout, missing-profile login must no longer create an active identity. This deliberately supersedes the earlier HU-03 auto-provisioning scenario. Build completion/discovery before deploying this gate. Preserve historical identities/admissions and update the exact missing-profile regression to expect denied access without using fixtures to pretend registration already happened.

### D5. Professional routes and payloads

Add professionals/urls.py, include at /professionals/, namespace professionals. Add a visible Professionals link for the administrative group independent of is_staff.

| Method / path | Name | Behavior |
|---|---|---|
| GET /professionals/ | index | 20-row active completed list; visible status=inactive and status=incomplete tabs; search/register links. Inactive tab contains completed inactive rows; incomplete tab contains all incomplete rows. |
| GET /professionals/search/ | search | Exact-DNI search; unmatched result offers prefilled registration. |
| GET /professionals/search/results/ | search-results | HTMX result fragment: full name, license, one detail link. |
| GET/POST /professionals/register/ | register | Username plus required profile data; supports new or incomplete identity. GET username permits exact account lookup for verification history; invalid username gets field feedback without exposing an account directory. |
| GET /professionals/<pk>/ | detail | Profile, eligibility/expiry, verification history, appropriate maintenance links. |
| GET/POST /professionals/<pk>/complete/ | complete | Incomplete only, fixed username, same registration service. |
| GET/POST /professionals/<pk>/edit/ | update | Mutable fields only. |
| GET/POST /professionals/<pk>/deactivate/ | deactivate | Confirmation. |
| GET/POST /professionals/<pk>/reactivate/ | reactivate | Confirmation, fresh verification. |
| POST /professionals/api/ | api-create | Registration/completion by username. |
| GET /professionals/api/search/?dni=... | api-search | {"results":[]} or one {id,full_name,license_number}. |
| GET/PATCH /professionals/api/<pk>/ | api-detail | Retrieve or edit; PATCH cannot complete a profile or change identity/status. |
| POST /professionals/api/<pk>/deactivate/ or reactivate/ | api-deactivate, api-reactivate | {"confirm":true}; client license status is never accepted. |

Create payload: username,dni,first_name,last_name,date_of_birth,license_number,specialty_code,hospital_service_code. Dates: YYYY-MM-DD. Detail: id,username,dni,registration_number,first_name,last_name,date_of_birth,license_number,specialty_code,hospital_service_code,license_status,license_verified_at,license_valid_until,registration_completed_at,is_active,is_clinically_eligible. Timestamps: ISO 8601 UTC; incomplete values: null. No embedded unbounded verification history.

API statuses: new profile 201; completion/update/status change 200; fields/immutable/unknown write keys 400 with {"field":["message"]}; anonymous/wrong role 403; missing professional 404 after role authorization; identified identity conflicts 409 with conflicting field errors plus existing_professional_id; negative license result 400 on license_number; unavailable/stale result 503 with code=license_verification_unavailable and generic detail. PUT/DELETE unsupported (405).

HTML anonymous GET redirects through application login with safe next; wrong role is 403. Successful ordinary POST redirects to detail. HTMX success contains status and detail link; bound field/duplicate errors return a 422 fragment preserving input; provider failure returns visible 503 retry feedback with explicit HTMX swapping. Keep patient API contracts unchanged.

### D6. Care relationships have a visible administrative workflow

CareRelationship in clinical_records/models.py: protected patient/Professional FKs, assigned_by User/PROTECT, assigned_at server time, is_active, nullable revoked_at/revoked_by. Enforce one active pair and consistent revocation metadata. Reassignment creates a new row; never overwrite revoked history.

Add Care team to administrative patient detail. GET /patients/<pk>/care-team/ lists active assignments (20/page), offers exact professional-DNI lookup and Assign form. POST submits professional_dni to assign_care_relationship(actor, patient, professional_dni). Active patient and eligible professional required. Duplicate active assignment returns the existing row idempotently. Revoke opens GET/POST /patients/<pk>/care-team/<relationship_pk>/revoke/, requires confirmation, verifies the relationship belongs to that patient, and calls revoke_care_relationship(actor, patient, relationship, confirmed).

API: GET/POST /patients/api/<pk>/care-team/ and POST /patients/api/<pk>/care-team/<relationship_pk>/revoke/. New 201; existing assignment/revocation 200. Output {id,patient_id,professional_id,professional_registration_number,is_active,assigned_at,revoked_at}; GET uses D7 pagination envelope. Bad/ineligible DNI 400; wrong role 403; missing administrative target 404. Implement clinical_records/care_services.py and care_views.py and wire from patients/urls.py. Administrative care-team privilege does not permit reading intervention notes.

Global domain lock order: subject professional User -> Professional -> Specialty -> HospitalService -> Patient -> CareRelationship -> Intervention; skip irrelevant rows and sort multiple same-model rows by PK. Registration/reference reassignment locks the selected reference rows in this order. Patient deactivation locks Patient then its relationships; professional deactivation locks User/Professional then its relationships. Neither path acquires preceding locks after later ones. An operation authorized before revocation may finish; revocation waits. A queued/new operation must recheck after revocation commits and be denied. Admission does not implicitly assign care. Reactivation does not restore revoked relationships.

### D7. Minimal intervention note and preserved correction

Intervention is a plain-text note, not a diagnosis/prescription. Fields: protected patient/author Professional, note (trimmed 1..4000 characters), server created_at, nullable self OneToOne supersedes/PROTECT, correction_reason (empty on original, trimmed 1..500 on correction). Records are immutable. A correction targets the current end of the same patient's correction chain. Unique supersedes prevents concurrent branches; the losing correction returns 409. Never render note text as executable HTML/Markdown.

Reject updates/deletes through normal model and QuerySet operations. Leave Intervention unregistered in Django Admin; creation, correction, and inspection use the audited product services. Database enforcement of ordinary SQL immutability is mandatory for AuditEvent under D8.

Any eligible professional currently assigned to that active patient may create or correct; being the original author is not an access bypass. Add My patients navigation: GET /clinical-records/my-patients/ lists only the actor's active assigned patients with name/DNI and View interventions links. GET/POST /clinical-records/patients/<patient_pk>/interventions/ lists/creates. GET/POST /clinical-records/patients/<patient_pk>/interventions/<intervention_pk>/correct/ shows the original and accepts note,correction_reason. Offer Correct only on the chain end; display originals/corrections newest first, labeling replacements. Successful ordinary POST redirects to the list; HTMX displays saved status and list link.

Implement intervention_services.py, intervention_views.py, intervention_forms.py, intervention_serializers.py under clinical_records. Services list_interventions, view_intervention (correction-form GET), create_intervention, correct_intervention accept actor, requested patient/target IDs, and submitted fields; authorization, application-field validation, and all object access go through D8. Forms/serializers map input but must not return field errors before entering the audited boundary. URL names in existing namespace: my-patients, patient-interventions, correct-intervention, api-patient-interventions, api-correct-intervention. API equivalents: GET/POST /clinical-records/api/patients/<patient_pk>/interventions/ and POST /clinical-records/api/patients/<patient_pk>/interventions/<intervention_pk>/correct/.

List envelope: {count,next,previous,results}; next/previous URL or null; page size 20. Each note: {id,note,author_registration_number,created_at,supersedes_id,correction_reason}. Creation/correction 201. Injected patient/author/timestamp/identity fields or unknown write fields: 400. Field errors in HTML/HTMX: bound 422 fragment. PUT/PATCH/DELETE: 405; correction is a new entry. Stable note ordering: created_at DESC,id DESC. Invalid page text -> page 1; out-of-range numeric page -> last page, matching current Paginator.get_page. No client-selected page size. Professional lists use last_name,first_name,id; My patients uses patient last_name,first_name,id; assignment lists use assigned_at DESC,id DESC.

Authenticated requests for unlinked, inactive, or nonexistent patient interventions all return the same generic 403. Missing/wrong-patient intervention target within an otherwise authorized patient is 404. Anonymous HTML read redirects to login after denial audit; anonymous API returns 403. Resolve count and records only after authorization.

### D8. Commit audit events without a permission or rollback bypass

AuditEvent fields: immutable id/server timestamp; nullable actor User/PROTECT, Professional/PROTECT, authorized Patient/PROTECT, target Intervention/PROTECT; nullable requested_patient_id/requested_intervention_id positive integers; action (intervention.list, intervention.view, intervention.create, intervention.correct); outcome (allowed, denied, invalid, conflict); bounded reason code; nullable result_intervention/PROTECT. For create, target/result is the new entry; for correction, target is old and result is new. Do not store note text, correction prose, DNI, credentials, or tokens in audit metadata/logs.

For unknown/anonymous identity, store null rather than fabricated IDs. Requested IDs preserve attempts at nonexistent objects. Before authorized object resolution, leave patient/target FKs null; do not query confidential objects merely to fill audit fields. Internal reasons: unauthenticated, role_required, profile_ineligible, relationship_required, invalid_input, concurrent_change. Public denial remains generic.

One orchestration boundary in audit/services.py is used by BOTH HTML and API intervention services. Resolve eligibility, lock/recheck clinical context, evaluate reads or perform writes, insert one event, and commit before returning data. Never return lazy querysets that query after locks are released. Correction-form GET is intervention.view; list GET is intervention.list; POST has its mutation action. A redirect's subsequent GET is a distinct read event, not a duplicate mutation event.

Log authorization denials before login redirects/API 403. Do not put login_required or a DRF role check in front of this boundary so it never sees denied reads. Intervention API views may explicitly set outer AllowAny ONLY because the audited service always authorizes; keep SessionAuthentication/CSRF and default protections everywhere else. Test anonymous GET at HTTP boundaries. Transport rejection before domain dispatch (CSRF, malformed HTTP/JSON, unsupported methods) is outside clinical-audit coverage; never disable CSRF to create an event. My patients membership discovery is not an intervention consultation; it reveals no notes and uses normal eligibility checks.

Catch expected authorization/domain errors within the outer atomic block; roll back partial mutations using a savepoint; insert the denied/invalid/conflict event; exit and commit normally; only then return/raise the HTTP error. Letting the denial escape before commit would erase its audit. An audit insert failure rolls back permitted mutations and returns 503 {"code":"audit_unavailable","detail":"Clinical access is temporarily unavailable."} without clinical content. Emit a content-free operational error; a failed audit store cannot record its own outage. No automatic mutation retries.

Make model/admin read-only and use PostgreSQL BEFORE UPDATE/DELETE triggers rejecting audit-row changes. ORM bulk operations and ordinary SQL must not bypass append-only behavior. No public audit API. An explicitly authorized Django audit operator can inspect events in read-only Admin; DB owners/migration operators remain trusted. Tests must cover denial survival, audit-write rollback, and SQL update/delete rejection.

### D9. Browser acceptance and fixture integrity

Product journeys start signed out at /, use visible Sign in/navigation, and known usernames/DNIs. Users have only required groups and is_staff=False. Explicit account provisioning, audit inspection, and legacy regression may start at /admin/login/ with an appropriate operator.

| Key | Initial state -> visible actions -> outcome |
|---|---|
| B1 new professional | Active account, no medical role/profile -> application admin registers by username with valid registry data -> one profile/number and medical group; fresh clinical login succeeds. |
| B2 legacy upgrade | Incomplete profile with existing admission -> admin Incomplete tab -> complete -> same profile/admission FK. Inactive variant remains inactive until Reactivate. |
| B3 failures | Missing fields, canonical duplicate, unknown/mismatched/expired/suspended/unavailable license -> specific feedback, no activation/group change; performed verification persists. |
| B4 lifecycle | Complete active profile -> edit/search/deactivate/reactivate with fresh verification -> immutable identity preserved; expiry/DNI conflict rejects reactivation. |
| B5 care | Active patient and eligible professional, NO relationship -> admin Patient search -> detail -> Care team -> assign by DNI -> one active pair; duplicate submit unchanged. |
| B6 intervention | Professional from B5 signs in fresh -> My patients -> View interventions -> empty state -> create -> correct -> original and linked correction plus matching audit events persist. |
| B7 revoked/denied | Admin revokes via Care team -> fresh professional login -> patient absent from My patients; bookmarked target denied/audited. Cover inactive user/profile/patient and unrelated actor separately. |
| B8 pages | Existing 21+ records -> visible Next/Previous in professional lists, care teams, My patients, intervention history, and retained patient/admission pages -> correct bounded ordered results. |
| B9 audit faults | HTTP integration: anonymous/unknown targets, conflicts, injected audit-write failure -> generic response, accurate nullable/requested IDs, no partial clinical mutation. |

B1/B2/B5/B6 must establish their target state through UI, never ORM fixtures. Synthetic registry/reference records and unrelated histories for B8 may be seeded. Provision unrelated completed personas through the registration service. Old-state fixtures are valid when migration/denial of that exact state is under test. Update isolated browser tests AND disposable Compose acceptance plus persistence verification. Browser-only factories cannot stand in for a missing assignment/registration workflow.

### D10. Operations and performance

Keep current production hosts/secret requirements, Gunicorn, WhiteNoise compressed static serving, development runserver, and proxy trust opt-in. Do not restore manifest storage without providing the vendor source maps it requires. Use the bundled validate_live_app.py: disposable production-mode Compose, isolated Chromium, real HTTP journeys, static/host checks, secure deployment checks, persisted verification, owned-resource cleanup.

Use deterministic synthetic local registry entries; no wildcard valid licenses. Acceptance seeding remains forbidden against production/shared data. A disposable validator may invoke its development seed command before serving the production-mode container.

For HU-05 search, use 10,000 completed synthetic profiles, 40 authenticated HTTP-boundary requests, nearest-rank p95 <2.0s, and record timing/environment. Reuse patients/test_search.py. Verify representative PostgreSQL query plans without forcing sequential scans off. Read-only search does not call the registry. Log no DNI, note, contact, license, or verification payloads in routine request/application logs; avoid raw query strings in production access-log formats for lookup endpoints.

## Risks / Trade-offs

- **[Legacy access]** HU-04 intentionally blocks unverified placeholders. Provide in-place completion and clear explanation; ship the completion UI and gate together.
- **[Registry fidelity]** Educational verification is a snapshot, not authoritative continuous licensure monitoring. Label that boundary.
- **[Audit availability]** Intervention access depends on audit writes. Fail closed with 503, preserve confidentiality, and test rollback.
- **[Concurrency]** Activation, deactivation, assignment, and correction overlap. Follow lock order, constraints, and real PostgreSQL interleaving tests.
- **[Scope growth]** Keep clinical authoring to note/correction; no prescriptions, diagnoses, appointments, or admission amendments.

## Migration Plan

1. Add nullable professional fields, sequence, registry/verification tables, and constraints after existing migrations. Preserve IDs, user links, active flags, and admissions. Test upgrade with both active/inactive minimal profiles and existing admissions.
2. Build completion, administrative discovery, and D4 eligibility as one HU-04 release slice. No fabricated data backfill and no gate-only deployment.
3. Update acceptance personas through supported registration; preserve exact incomplete/inactive/no-role/legacy regressions instead of replacing them with perfect fixtures.
4. Add care relationships, then intervention/audit schema and triggers, then audited routes. Never expose intervention operations before both authorization and auditing exist.
5. Forward/backward migration tests use disposable databases. Empty-schema reversal is testable; after professional/clinical/audit writes, prefer forward fixes or isolated backup restoration. Do not suggest dropping populated clinical schema as routine rollback.
6. Complete tasks.md gates, full PostgreSQL tests, and disposable Compose validation. Planning completion does not mean implementation completion.
