## Context

See `proposal.md` for motivation and the two capability specs for behavior. The repository has no application implementation yet. The selected implementation platform is a Python 3.13 modular monolith built with Django 5.2 LTS, Django REST Framework 3.18, PostgreSQL 18, and server-rendered Django templates enhanced with HTMX and Bootstrap 5. The source assignment expects incremental one-week sprints, complete CRUD for patient and professional modules, privacy-aware access, auditability, and later integration with appointments, electronic health records, and FHIR.

## Goals / Non-Goals

**Goals:**

- Keep patient and professional workflows independently implementable while sharing identity, validation, authorization, and auditing conventions.
- Give every team member a reproducible local environment and one-command quality checks.
- Preserve stable identifiers and clinical traceability across updates and deactivation.
- Make each story demonstrable and testable at the end of its assigned sprint.
- Leave clear integration points for later appointment and clinical modules.

**Non-Goals:**

- Building a separate single-page application, independent microservices, or a production orchestration platform during Epics 1 and 2.
- Building appointment agendas, reminders, complete authentication, full electronic health records, FHIR resources, or external interoperability.
- Physically deleting records that may be referenced by clinical or audit data.

## Decisions

### Adopt Django, DRF, PostgreSQL, and server-rendered HTMX

Use Python 3.13 with Django 5.2 LTS for the application and ORM, Django REST Framework 3.18 for explicit API contracts, and PostgreSQL 18 for all development, test, and deployed relational storage. Render the initial user interface with Django templates, Bootstrap 5, and small HTMX interactions. This stack supplies migrations, validation, sessions, CSRF protection, permissions, administrative tooling, and test utilities while keeping one deployable codebase. A React single-page application was rejected for these epics because it would duplicate routing, validation, authentication integration, and build tooling without an assignment requirement for a rich client.

### Standardize development and quality tooling

Manage Python and locked dependencies with `uv`. Run the application and PostgreSQL locally through Docker Compose. Use pytest with pytest-django and DRF test helpers, Playwright only for critical browser workflows, Ruff for linting and formatting, mypy for targeted static checks, pre-commit for local enforcement, and GitHub Actions for continuous integration. Publish the DRF contract as OpenAPI using drf-spectacular. SQLite is rejected even for routine development because its constraints, concurrency, and query behavior differ from the target database.

### Use a modular monolith for the MVP

Start with one Django project separated into apps with the canonical labels `patients`, `professionals`, `clinical_records`, `access_control`, and `audit`. Keep domain rules in application services rather than templates or DRF view classes. This minimizes operational overhead for a student MVP while preserving boundaries that can later become services. Independent microservices were rejected because they add deployment and consistency work before the domain is stable.

### Assign each Django app clear domain ownership

- `patients` owns patient identity, demographics, contact information, insurance information, and active status.
- `professionals` owns professional identity, licenses, specialties, hospital services, and active status.
- `clinical_records` owns admissions, vital-sign observations, care relationships, and interventions that connect patients with professionals.
- `access_control` owns shared authorization policies and actor-context integration; it does not duplicate patient or professional profiles.
- `audit` owns append-only access and modification events that reference records owned by the other apps.

### Use Django sessions for the browser and DRF for stable contracts

Use Django session authentication and CSRF protection for the same-origin browser interface. Apply Django groups and explicit DRF permission classes to administrative and professional operations, including object-level care-relationship checks for HU-06. DRF serializers define external input/output contracts even when an HTMX form is the first consumer. JWT is deferred because the current product has no separate mobile or third-party client.

### Model stable identity separately from mutable profile data

Patient and professional internal identifiers and generated record numbers are immutable. DNI, demographics, contact data, specialty, service, and status are validated domain attributes. Database uniqueness constraints back application validation for DNI, clinical record number, registration number, and license number so concurrent requests cannot create duplicates.

### Use deactivation as delete behavior

CRUD delete actions change an entity to inactive rather than physically removing it. This satisfies administrative lifecycle needs while preserving admissions, intervention links, and audits. Hard deletion was rejected because it would break traceability and later clinical-record integrity.

### Separate admission events from the patient profile

Each `clinical_records.Admission` is an immutable event linked to one `patients.Patient` and one `professionals.Professional`, with consultation reason, vital signs, and server timestamp. Corrections create an auditable amendment rather than silently replacing clinical values. Storing the latest vital signs directly on the patient was rejected because it would erase history.

### Isolate license validation behind a provider boundary

Professional registration calls a license-status provider. The initial MVP can use a controlled local registry supplied for testing; a real registry can replace it without changing registration behavior. Fail-closed behavior prevents activation when validity is negative or unavailable.

### Require a validated professional context for HU-06

HU-06 uses the application's authenticated actor context and verifies active professional status plus a stored care relationship before returning intervention data. This is the minimum security slice required by Epic 2; broader identity and role administration remains in the future security epic.

### Make clinical-access auditing append-only

Consultation and modification attempts produce audit events containing server time, actor, patient, action, target, and outcome. Audit events are not exposed through normal update/delete operations. Recording denied attempts supports privacy investigation as well as the assignment's traceability criterion.

### Design exact-DNI search for indexed lookup

Store DNI values in their canonical 7-or-8-ASCII-digit format and query them through a unique index. For search input, trim leading and trailing whitespace before validating the canonical value; continue to reject punctuation, internal whitespace, and other noncanonical characters. Measure the two-second requirement at the application boundary under a documented MVP-size dataset, including authorization and serialization. Broad fuzzy search is deferred.

### Keep FHIR at an interoperability boundary

Model the hospital domain relationally in Django rather than storing FHIR resources as the primary database representation. A later interoperability app can map stable domain models to resources such as Patient, Practitioner, Encounter, and Observation through DRF endpoints. Embedding FHIR JSON in the core tables was rejected because Epics 1 and 2 do not require FHIR and doing so would couple basic CRUD to an incomplete interoperability design.

## Risks / Trade-offs

- **[Risk] The assignment does not define vital-sign ranges.** -> Keep ranges configurable, document the initial medically plausible bounds, and test boundary behavior.
- **[Risk] Framework and tool versions can drift across machines.** -> Commit `uv.lock`, pin container image major versions, and make CI the reproducibility reference.
- **[Trade-off] Server-rendered HTMX offers less client-side freedom than a SPA.** -> Keep DRF contracts independent so a richer client can be added later without replacing domain logic.
- **[Risk] No authoritative license registry is identified.** -> Use a provider interface and controlled test registry; clearly label non-production validation.
- **[Risk] HU-06 depends on authentication planned for a later epic.** -> Implement only the minimal actor/session boundary needed to validate a professional and keep full account management out of scope.
- **[Risk] The preliminary backlog mislabels HU-04 through HU-06 as appointment functions.** -> Follow the later detailed Epic 2 tables, which explicitly define professional management and acceptance criteria.
- **[Trade-off] Soft deletion retains more data.** -> Restrict access to inactive records and define retention/privacy policy before production use.

## Migration Plan

1. Pin Python and dependencies with `uv`, scaffold the `patients`, `professionals`, `clinical_records`, `access_control`, and `audit` Django apps, and configure Docker Compose with PostgreSQL 18.
2. Configure Django sessions, DRF, OpenAPI, templates, HTMX, Bootstrap, pytest, Ruff, mypy, pre-commit, and CI.
3. Introduce lookup/reference data for specialties, services, and the MVP license registry.
4. Create patient, professional, admission, care-relationship, intervention-reference, and audit storage with uniqueness and foreign-key constraints.
5. Deliver the sprint slices in order: HU-01/HU-02, HU-03, HU-04/HU-05, then HU-06.
6. Seed non-sensitive demonstration data and run acceptance, authorization, audit, and performance tests against PostgreSQL.
7. Roll back application behavior by deployment version; use reversible Django migrations and preserve created clinical and audit data unless an explicit migration safely removes unused schema.
