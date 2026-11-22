# End-to-end acceptance · 22 November 2026

| Environment | Result | Evidence |
| --- | --- | --- |
| PostgreSQL non-browser suite | 411 passed | Two distinct PostgreSQL connections competed for the same slot. Exactly one reservation committed. Controlled-clock tests exercised the 24-hour reminder boundary, concurrent delivery claims and retry behavior against a test mailbox. |
| Isolated Django test server | 43 Chromium tests passed, 0 skipped | Fresh browser contexts exercised the journeys below. A running reminder worker delivered to a local SMTP mailbox. Database assertions reopened the linked request, appointment, contact history, reminder, care relationships, documentation and audit records. |
| Running Compose application | 40 Chromium journeys passed, 0 skipped | The validator built and migrated disposable project `helixhealth-validation-f1b90a0d5767`. Chromium used the web service over HTTP. The scheduler delivered to the Compose SMTP mailbox. The in-container `verify_acceptance` command passed before the validator removed the project and its volume. |

Each role started signed out at `/` and signed in through the visible link. The account administrator provisioned the scheduling and reception roles and assigned audit permissions through account management. The journeys used synthetic patients and clinic-local dates.

## Scheduling

| Stories | Role and visible actions | Result |
| --- | --- | --- |
| HU-12, HU-14 | The schedule manager used **Manage availability** to open a dated schedule with ten-minute slots. A reception-only operator searched by date and specialty, selected the named professional and time, and verified the supplied DNI and birth date. | The selected interval was available before reservation and appeared under the selected professional in the daily agenda afterward. |
| HU-15, HU-13 | Reception opened a phone request for DNI `20000018`, recorded an unanswered call, saved a pending reservation, and recorded the subsequent phone confirmation. Two operators then selected and occupied a proposed move destination before the original move was submitted. | The move form reported that the opening was unavailable. PostgreSQL retained one request and one appointment for this patient, both contact outcomes, and the original professional and interval throughout the appointment history. |
| HU-17 | Once the booking was confirmed inside the reminder window, reception reopened the agenda while the scheduler polled. | The mailbox received exactly one email for this patient containing the booked professional, date, time and clinic time zone. PostgreSQL recorded one sent attempt between confirmation and arrival. Separate bookings exercised a missing email address and an uncertain SMTP acknowledgment. |
| HU-18, HU-11 | A second reception-only operator reopened **Daily agenda**, verified the patient's identity and recorded arrival. The original operator reloaded the agenda. Separate visits exercised cancellation and absence, including premature absence and a stale cancellation after arrival. | The original visit appeared once as **Attended** with its check-in operator. Its history was reserve → confirm → arrival. The other visits retained their respective canceled, attended and absent states. The main Compose journey ended at `/appointments/?day=2026-11-22&professional=6`. |

## Clinical chart and audit

| Stories | Role and visible actions | Result |
| --- | --- | --- |
| HU-19 | The care coordinator used **Patient search** and **Care team** to assign active physicians to the patient with DNI `20000016`. The physicians entered via **Assigned patient charts**. | Booking and arrival alone left the physician outside the chart. Assignment exposed the chart and administrative admission. Cancellation of a separate visit preserved chart access. |
| HU-20, HU-22 | One assigned physician recorded the consultation, personal history and initial family history. A colleague reopened the consultation, added a progress note and corrected the family relationship from Mother to Sister. | PostgreSQL retained one consultation, the separately authored note, the personal history and both family revisions with their authors. The stale correction was rejected. |
| HU-21 | An assigned physician imported the same FHIR bundle twice. The colleague opened the requested procedure from the clinical timeline and inspected its clinical date, requester and external identifier. | One requested procedure appeared in clinical-date order. The admission identified its administrative recorder. The imported identifier matched the one preserved in the audit event. |
| HU-23 | A treating physician with audit permission reviewed the import origin and submitter. Administrative and treating auditors filtered the history and opened the correction's before and after values. The coordinator then revoked an assignment while the physician had a note form and audit detail open. | Reception and the physician without an audit grant received HTTP 403. Revocation denied both the next note submission and the open audit detail on reload. The revoked physician returned to `/clinical-records/charts/`, where the patient was absent. |

Ruff formatting and lint, mypy, Django system and migration-drift checks, the Compose deployment check and strict OpenSpec validation passed. The live gate ran with `uv run python .agents/skills/validate-live-app/scripts/validate_live_app.py`.
