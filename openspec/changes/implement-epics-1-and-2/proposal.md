## Why

OpenHIS-UNLaM needs a reliable administrative foundation for identifying patients and professionals before appointment, clinical-record, and interoperability modules can be built. The assignment defines Epics 1 and 2 as the first four one-week sprints and requires a professional-quality MVP with validation, traceability, documentation, and tests.

## What Changes

- Add complete patient lifecycle management, including registration, lookup, detail access, updates, and safe removal/deactivation.
- Add patient admission records containing consultation reason and vital signs, automatically timestamped and attributed to the recording professional.
- Add complete professional lifecycle management, including specialty and service assignment, unique identifiers, and active-license validation.
- Add fast professional lookup and detail access to support later agenda workflows without implementing appointment management.
- Add authorized access to a professional's patient interventions and audit every consultation or modification.
- Define small, independently verifiable implementation tasks organized across Sprints 1 through 4.

## Capabilities

### New Capabilities

- `patient-management`: Patient CRUD, unique identity and clinical-record numbering, DNI lookup, and admission vital-sign capture for HU-01 through HU-03.
- `professional-management`: Professional CRUD, specialty/service assignment, DNI lookup, license validation, authorized intervention access, and audit logging for HU-04 through HU-06.

### Modified Capabilities

None.

## Impact

- Establishes a Python 3.13 modular monolith using Django 5.2 LTS, Django REST Framework 3.18, server-rendered Django templates enhanced with HTMX and Bootstrap 5, and PostgreSQL 18.
- Adds reproducible local development through `uv` and Docker Compose, with pytest-based testing, Ruff, mypy, pre-commit, OpenAPI documentation, and GitHub Actions CI.
- Introduces patient, admission, vital-sign, professional, specialty, service-assignment, intervention-access, and audit-log data contracts.
- Requires user interfaces and application/API operations for administrative and professional workflows.
- Requires persistence constraints for DNI, clinical-record number, professional registration number, and license number.
- Requires automated tests for validation, authorization, auditability, and the two-second search acceptance target.
- Excludes appointment scheduling, SMS/email reminders, full electronic health records, beds/inpatient management, billing, and interoperability standards from this change.
