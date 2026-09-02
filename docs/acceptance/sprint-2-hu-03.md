# Sprint 2 HU-03 Acceptance Evidence

## Scope

HU-03 allows an authenticated active medical professional to record an
admission for an active patient. The admission contains a consultation reason,
systolic and diastolic blood pressure, heart rate, temperature, the creating
professional, and a server timestamp.

The initial configurable vital-sign bounds are:

| Vital sign | Minimum | Maximum | Unit |
| --- | ---: | ---: | --- |
| Systolic blood pressure | 70 | 250 | mmHg |
| Diastolic blood pressure | 40 | 150 | mmHg |
| Heart rate | 30 | 220 | bpm |
| Temperature | 30.0 | 45.0 | degrees Celsius |

Deployments can replace the complete `CLINICAL_VITAL_SIGN_RANGES` settings
mapping without a schema migration.

## Acceptance Walkthrough

### Enter the medical-professional workspace

1. Start signed out at the HelixHealth home page and select **Sign in**.
2. Sign in with a non-staff user in the Medical Professionals group that does
   not yet have a professional profile.
3. Confirm that login redirects directly to **Clinical workspace**.
4. Confirm that login persisted one active minimal professional identity for
   the account.
5. Confirm that every active patient is listed with DNI, full name, clinical
   record number, and a **Record admission** action.
6. Confirm that inactive patients are absent.

Evidence:

- `test_non_staff_medical_role_login_provisions_profile_and_opens_workspace`
- `test_medical_role_login_with_workspace_next_provisions_profile`
- `test_application_login_does_not_reactivate_inactive_professional`
- `test_authenticated_medical_role_on_home_is_redirected_and_provisioned`
- `test_medical_role_without_active_profile_cannot_open_workspace`
- `test_anonymous_workspace_request_redirects_to_application_login`
- `test_clinical_workspace_lists_all_active_patients_and_excludes_inactive`
- `test_medical_professional_records_admission_through_ui`

### Redirect the legacy Django Admin entry path

1. Open `/admin/login/` signed out, matching the previously reported entry path.
2. Sign in with a staff user in the Medical Professionals group that has no
   professional profile and no Django model permissions.
3. Confirm that the browser passes through `/admin/` and lands on **Clinical
   workspace** instead of the empty Django administration page.
4. Confirm separately that a medical staff user with an actual Django model
   permission remains in Django Admin.

Evidence:

- `test_staff_medical_professional_admin_login_redirects_to_clinical_workspace`
- `test_medical_staff_user_with_admin_permission_stays_in_django_admin`
- `test_legacy_admin_login_redirects_medical_professional_to_workspace`

### Select a patient without an internal ID

1. Use **Record admission** in the medical navigation.
2. Search with the active patient's exact DNI.
3. Confirm that the result shows the patient's full name and clinical record
   number.
4. Use **Record admission for _patient name_** to open the form in one click.
5. Repeat with an unmatched DNI and an inactive patient's DNI; confirm that no
   admission action is offered.

Evidence:

- `test_medical_professional_records_admission_through_ui`
- `test_medical_search_finds_active_patient_and_links_to_admission_form`
- `test_medical_search_does_not_offer_admission_for_missing_or_inactive_patient`
- `test_medical_search_reports_invalid_dni_and_rejects_non_professional`

### Valid admission record

1. Authenticate through the HelixHealth application login as a user in the Medical
   Professionals group with an active professional profile.
2. Find the active patient by DNI and open the admission form from the result.
3. Enter a consultation reason, complete blood pressure, heart rate, and
   temperature within the accepted ranges.
4. Submit the HTMX form.
5. Confirm that the success result and refreshed admission history display the
   persisted values, authenticated professional username, and server timestamp.

Evidence:

- `test_medical_professional_records_admission_through_ui`
- `test_htmx_success_displays_the_persisted_admission_metadata`
- `test_administrative_patient_record_displays_saved_admission`

### Missing or invalid admission value

1. Leave diastolic blood pressure empty and enter systolic blood pressure above
   its configured maximum.
2. Submit the HTMX form.
3. Confirm that both fields display specific errors and that no admission is
   present.
4. Repeat at every minimum, maximum, and immediately out-of-range boundary for
   every vital sign.

Evidence:

- `test_medical_professional_records_admission_through_ui`
- `test_htmx_admission_reports_specific_missing_and_invalid_values`
- `test_vital_sign_boundaries_are_accepted`
- `test_out_of_range_vital_signs_are_rejected_atomically`
- `test_creation_rejects_blank_consultation_reason_atomically`

### Server-owned professional and timestamp

1. Submit the admission API payload with `professional_id` and `created_at`.
2. Confirm that the request is rejected and creates no record.
3. Resubmit without server-owned fields.
4. Confirm that the saved professional matches the authenticated profile and
   the timestamp falls between the server times immediately before and after
   creation.

Evidence:

- `test_api_rejects_server_owned_metadata_and_uses_authenticated_professional`
- `test_admission_persists_patient_professional_vitals_and_server_timestamp`

### Authorization and active status

1. Attempt admission creation anonymously, as an administrative actor, as a
   medical-role user without a professional profile, with an inactive
   professional profile, and for an inactive patient.
2. Confirm that each attempt is rejected and no admission is created.

Evidence:

- `test_creation_rejects_missing_wrong_inactive_and_unlinked_professional_actors`
- `test_creation_rejects_an_inactive_patient_without_partial_write`
- `test_api_authorization_rejects_anonymous_admin_and_inactive_professional`

## Verification Results

Run on 2026-09-01 against local PostgreSQL 18 and Chromium:

```text
uv run pytest clinical_records/test_admissions.py -q
34 passed

uv run pytest -q
145 passed

uv run ruff format --check clinical_records professionals patients access_control helixhealth tests
84 files already formatted

uv run ruff check .
All checks passed

uv run mypy
Success: no issues found in 50 source files

uv run python .agents/skills/validate-live-app/scripts/validate_live_app.py
6 browser workflows passed; live application validation passed
```

The primary browser workflow starts signed out at `/`, follows the visible
**Sign in** link, authenticates a non-staff professional, and lands directly in
the clinical workspace. It selects the patient from the active-patient list
without using Django Admin or an internal patient ID. It then exercises invalid
HTMX submission, persists a valid admission, and reloads the patient's admission
history to prove the record survived the request.

The reported legacy workflow starts signed out at `/admin/login/`, authenticates
a staff medical professional without Django model permissions, and verifies
that the real browser lands on `/clinical-records/` rather than the empty Django
administration index.

The local development account `medico` was also checked against the real
development PostgreSQL database. Before login it had the Medical Professionals
group but no professional identity. The real Django login request provisioned
that identity and redirected once to `/clinical-records/`, which returned 200.
An authenticated request from the same account to `/` also redirects to the
clinical workspace, covering a refresh of an already-open smoke page.
