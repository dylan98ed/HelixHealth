## Context

See proposal.md for motivation and the user-confirmed additive scope. The current application already has the diagram's patient fields and all its professional fields except an externally entered license number. `Professional.registration_number` is a generated `PR-` identifier, not the supplied example's `MN 123456`.

The in-progress `implement-epics-1-and-2` change owns patient/professional management. Its registration services and product UI are implemented; several professional API and clinical rollout tasks remain pending. This proposal adds a separate `professional-licensing` contract because no capabilities have yet been published under `openspec/specs/`. Existing requirements remain applicable; this additive contract supplies the additional license input/output rules wherever the older field lists are used.

## Goals / Non-Goals

**Goals:** add one independently stored field, preserve existing data and access, reuse the current administrative registration/edit workflows, and make the two professional numbers unambiguous.

**Non-Goals:** rename/remove existing fields; redesign account provisioning; introduce a licensing authority registry, license verification, multi-license management, or new access restrictions; implement unrelated pending professional APIs or HU-06 work. The diagram's full CRUD wording retains the current create/read/update/confirmed-deactivation semantics and history protections.

## Decisions

### 1. Use these English fields and preserve the existing extras

| Patient diagram field | English field | Action |
|---|---|---|
| ID | `id` | Keep generated immutable primary key |
| DNI | `dni` | Keep existing canonical identity rule |
| Name | `first_name` | Keep |
| Surname | `last_name` | Keep |
| Date of birth | `date_of_birth` | Keep |
| Sex | `sex` | Keep |
| Telephone | `phone` | Keep |
| Email | `email` | Keep |
| Address | `address` | Keep |

Patient also retains `clinical_record_number`, `health_insurer`, `is_active`, and existing clinical relationships. No patient schema migration is needed.

| Professional diagram field | English field | Action |
|---|---|---|
| ID | `id` | Keep generated immutable primary key |
| DNI | `dni` | Keep existing canonical identity rule |
| Professional license | `license_number` | Add entered text; label License number |
| Name | `first_name` | Keep |
| Surname | `last_name` | Keep |
| Specialty | `specialty` | Keep existing reference relationship |

Professional also retains `user`, `registration_number`, `date_of_birth`, `hospital_service`, `registration_completed_at`, `is_active`, and clinical relationships. `specialty_code` remains the form/API selector for the existing `specialty` relationship. The example's specialty corresponds to the existing General Medicine reference; no duplicate specialty table or free-text specialty field is added.

### 2. Add `license_number` independently of the generated number

Use a nullable, blank-capable `CharField(max_length=50)` so existing rows can retain an unknown value as NULL. Do not use an integer, a sequence, or a rename of `registration_number`: license text must retain prefixes, internal spaces, case, and leading zeroes. Add a named database check allowing NULL or a nonblank trimmed value. Reuse a shared validator/normalizer at write boundaries: require text, strip surrounding whitespace, reject empty/whitespace-only and more than 50 characters, preserve the remainder.

Do not add `unique=True` or infer jurisdiction from a prefix. The supplied request defines neither an issuing-authority key nor a uniqueness scope. Existing account, active-DNI, and generated-number uniqueness rules remain unchanged.

### 3. Require the new input for registration; preserve legacy completion state

Extend `register_professional` and new/incomplete registration forms with required `license_number`. Validate before generated-number allocation or profile/group writes. Extend the existing update allowlist with `license_number`; it is correctable by an authorized administrator rather than an immutable generated identifier. A partial update that omits it preserves its current value.

Keep `is_registration_complete`, registration timestamps, current clinical eligibility, and index state predicates compatible for previously completed records with NULL licenses. Recording a license does not prove or revoke clinical eligibility. New/completion service validation requires a valid license for new writes; the nullable column deliberately supports existing completed data without resetting timestamps or introducing a second migration-status flag.

For Edit professional, an untouched blank control on a legacy NULL license is omitted from service changes, allowing unrelated edits. Once a license exists, clearing it is an error. New registration/completion forms always require the field. API updates reject explicit null/blank and use omission to retain the current value. This avoids locking older records out of ordinary maintenance while never manufacturing a license.

### 4. Extend existing interfaces without changing identifier meanings

Show **License number** beside **Registration number** on detail/list/search results. For NULL values use **Not recorded**, while retaining the existing incomplete/active/inactive status labels. Add license inputs to the existing forms and bound field errors, preserving ordinary POST and HTMX behavior.

Registration service input adds `license_number`; professional update input accepts it; professional JSON detail/search results add `license_number` (string or null). Preserve every existing response key, including `registration_number`, `professional_registration_number`, and `author_registration_number`; these continue to mean the internal generated identifier. Do not rename patient fields or change their API contracts.

If professional serializers are still unimplemented at apply time, record this additive field in the existing change's pending API requirements/tasks rather than introducing a parallel API surface. If they exist, update them and their exact-contract tests in this change. The core model/service/HTML addition is independently implementable in either case. Existing completed task checkboxes describe historical work and are not evidence that this new field was implemented.

### 5. Validate real operator and user journeys

New registration starts with a login account provisioned through supported Django Admin controls and no professional profile or medical group. A separate fresh non-staff Administrative session starts at `/`, follows Professionals, and supplies the entered license and every existing required field. Verify failure without a license, success with `MN 123456`, saved detail, DNI search, and fresh clinical login. Never seed the target license or role assignment.

A legacy scenario starts with the old completed schema/state and linked admissions, verifies NULL license without state changes, then uses visible Edit to add/correct it. Exercise unrelated legacy edits, active/inactive status preservation, completion of an incomplete row, and unchanged patient fields. Use both isolated PostgreSQL Chromium tests and the disposable Compose validator with database persistence verification.

## Risks / Trade-offs

- Required new input breaks old registration callers: update fixtures, service call sites, forms, and any existing serializers atomically in the implementation change.
- NULL permits historical unknown licenses: display that state explicitly, preserve existing access, and provide Edit rather than backfilling fictitious credentials.
- Two identifiers can confuse users: label them separately and keep all existing generated-number response keys stable.
- No jurisdiction-specific format/uniqueness is inferred: this is storage validation, not a claim that a license is authentic or globally unique.

## Migration Plan

1. Add a migration after the current professional migration leaf (currently `0005_professional_registration_number_sequence`); add only the nullable license column and its NULL-or-nonblank check. Do not rewrite historical migrations or remove fields/sequences.
2. Validate a forward upgrade with active/inactive complete/incomplete profiles, user links, generated numbers, timestamps, and admissions. All existing values must remain unchanged; licenses start NULL.
3. Deploy updated service/form/template contracts together. Existing completed rows can be maintained without a license; all new registrations/completions collect one.
4. Update current acceptance callers and any available professional API clients before enabling the required input. Preserve the separate clinical-eligibility rollout queue.
5. Test reverse/forward migration only on an empty disposable database. After license data is entered, roll application code back while retaining the additive nullable column, or make a forward repair; dropping populated license data is not a routine rollback.
