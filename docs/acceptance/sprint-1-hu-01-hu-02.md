# Sprint 1 HU-01/HU-02 acceptance evidence

## Scope

This walkthrough covers patient registration, validation, duplicate prevention,
detail display, maintenance/deactivation, exact-DNI search, direct detail access,
and the unmatched-DNI registration action.

The documented MVP search dataset contains 10,000 active patients. The
application-boundary measurement performs 40 authenticated requests against the
exact-DNI DRF endpoint and computes the nearest-rank p95. The acceptance limit is
less than two seconds.

## Automated walkthrough

Run the focused acceptance and performance coverage against local PostgreSQL:

```text
uv run pytest patients/test_patient_model.py patients/test_validation.py patients/test_services_api.py patients/test_views.py patients/test_search.py -q -s
```

Run the real-browser workflows, which authenticate through the UI and cover both
registration and search-to-detail/search-to-prefilled-registration paths:

```text
uv run pytest tests/test_browser_workflows.py -m browser -q
```

The complete live validation command is:

```text
uv run python .agents/skills/validate-live-app/scripts/validate_live_app.py
```

Focused PostgreSQL verification on 2026-08-30 passed 49 tests. The measured
exact-DNI endpoint p95 was 0.003286 seconds for the 10,000-patient dataset, and
PostgreSQL selected `unique_active_patient_dni` for the lookup plan.

The bundled live validator passed all four Chromium workflows on 2026-08-30,
with no skipped browser scenarios.

## Traceability

| Acceptance scenario | Evidence |
| --- | --- |
| Valid registration creates identifiers and displays the record | `test_patient_service_creates_one_complete_patient_transactionally`, `test_administrative_user_registers_patient_through_ui` |
| Invalid or missing registration values identify fields and create no record | `test_htmx_registration_identifies_each_invalid_field`, `test_invalid_registration_does_not_allocate_clinical_record_number` |
| Duplicate active DNI is rejected with a record action | `test_patient_service_rejects_duplicate_dni_without_partial_write`, `test_duplicate_registration_links_to_existing_patient` |
| Mutable data changes without changing identifiers | `test_patient_update_api_changes_mutable_data_and_rejects_identifiers` |
| Deactivation preserves data and removes the patient from active results | `test_confirmed_deactivation_preserves_record_and_excludes_it_by_default`, `test_lookup_service_returns_exact_active_match_and_excludes_inactive` |
| Exact DNI returns full name and clinical record number | `test_search_api_returns_found_and_empty_result_shapes`, `test_htmx_search_result_links_to_patient_detail` |
| A search result opens complete patient details in one action | `test_administrative_user_searches_patient_and_prefills_registration` |
| No match offers registration, prefills DNI, and creates nothing automatically | `test_unmatched_dni_registration_action_prefills_without_creating`, `test_administrative_user_searches_patient_and_prefills_registration` |
| Indexed lookup meets the two-second p95 target | `test_exact_active_dni_query_uses_unique_index`, `test_patient_search_p95_is_below_two_seconds_for_mvp_dataset` |
