# Technical design · Medical appointments and the patient chart

## Context

The Django application stores patient, professional and specialty identities in PostgreSQL. The medical workspace currently renders a general patient directory. The administrative patient detail includes admissions and imported orders. The new reception lookup and the treating physician's chart each need their own query scope. The [approved story plan](../../../../docs/plan-epica-3-turnos-hce.md) supplies priorities and journey-level tests.

## Goals / Non-Goals

Keep four facts distinct: a patient requested a visit, a professional's time was reserved, reception saw the patient arrive, and a physician documented care. Each has its own author and timestamp. Automatic assignment, external messaging integrations, a patient portal and procedure-result capture are outside this change.

## Decisions

### 1. Entry points and permissions

Use Django's existing groups and session authentication. Add a Reception group to the role registry and provisioning migration. Add distinct permissions for schedule configuration and chart audit. Assign these through the supported account-management flow. Normal work proceeds from visible navigation after login at `/`. Accounts with multiple functions retain links to each authorized workspace.

| Proposed entry | Who can use it | Scope |
| --- | --- | --- |
| `/appointments/` | Reception | Daily agenda, slot search, booking, request inbox, contact outcomes and arrival |
| `/appointments/availability/` | Administrative account with schedule-management permission | Professional hours, durations and exceptions |
| Assigned patients in `/clinical-records/` → patient chart | Active medical account with completed active profile | Active patient and current care relationship, checked on every read, detail link and write |
| Chart audit from the administrative workspace or an authorized chart | Active administrative account with audit permission, or eligible treating professional with audit permission | Administrative cross-patient lookup, or the professional's current assigned patients only |

Use an exact, normalized DNI lookup for active patients within scheduling. Collect the second identifier supplied by the patient (date of birth) for server-side verification. Return only the identity and contact fields needed by reception. Keep the existing administrative patient detail restricted. Use a separate assigned-patient query in the medical dashboard. Never manufacture a care relationship from a booking, arrival or reschedule. Protect writes with session/CSRF checks and recheck eligibility inside the transaction. Provide the same decisions for full-page and partial responses.

### 2. Availability is derived, reservations are persisted

Add an `appointments` app. Store weekly availability as professional, weekday, local start/end, duration in minutes and effective date range. Model dated closures or replacement hours as exceptions. A replacement defines the whole day's availability. Validate positive duration, start before end and disjoint windows for coincident weekdays and effective dates. Professional-local rules allow adjacent intervals. Generate full slots on the grid starting from each window's opening time and subtract occupied intervals. Use the institution's scheduling timezone (proposed default `America/Argentina/Buenos_Aires`) for wall-clock input, day filtering and email display. Persist appointment instants as timezone-aware timestamps.

Each appointment stores protected patient and professional references, start, end, state, creator, update version and timestamps. Its append-only operational history records actor, time, old/new state and old/new professional and interval when applicable. Save the booking as the moment of occupation. Store request/contact attempts separately, with a unique optional link from a request to its resulting appointment. A request can exist before a professional or time is chosen.

| Action | From | Result |
| --- | --- | --- |
| Save reservation | Named free slot and identified patient | Pending, or confirmed if identity and confirmation were recorded together |
| Confirm | Pending | Confirmed on the same row after identity verification |
| Reschedule | Pending or confirmed | New selected free interval, retaining patient and current state |
| Register arrival | Pending or confirmed | Attended (*atendido*) immediately after identity check |
| Record absence | Pending or confirmed, appointment start reached | Absent |
| Cancel | Pending or confirmed | Canceled, with an operational history entry |

Treat attended, absent and canceled as final. Only cancellation releases a saved slot for reuse while it is still future and eligible. Keep attended intervals occupied even if reception checks in the patient early. Treat manual phone and WhatsApp contact as operator-entered events. Record contact channel, outcome, actor and time. A failed contact leaves the request pending.

### 3. One transaction protects a chosen slot

Implement booking, rescheduling and availability changes as domain service operations. Serialize schedule edits and booking checks on the affected professional row(s), locking multiple professionals in stable identifier order. Align locks on existing identity rows with the care services' established order (account, professional, patient, relationship when relevant). Re-read eligibility, interval, availability and expected appointment version under lock. For edits, reject a stale version and offer a refreshed view. Protect half-open appointment ranges `[start, end)` from overlap per professional using a PostgreSQL exclusion constraint, with a positive interval check and the `btree_gist` extension. Apply it to all states except cancellation. Adjacent times are valid. The transaction includes the appointment, request link if any and history entry. A failed move preserves the original reservation. Use an operation token to recognize a retried successful submission. A conflict returns fresh choices for the operator.

Serialize edits to overlapping schedule rules with the same professional lock. Closing hours in a future revision affects future offers. Show existing bookings outside the revised windows and preserve their original details.

### 4. Reminder delivery

Run a Django management command periodically in an independently started scheduler process, including in Compose. A one-minute polling interval is the proposed default. A run selects confirmed appointments where `now < start <= now + 24 hours`, including late confirmations and work missed by an earlier run. Use a durable delivery row keyed by appointment and schedule revision. Increment that revision on a move, including a change of professional. Keep ordinary state edits separate from schedule revisions. Recheck the current recipient, revision, start and state before dispatch. Mark older pending deliveries obsolete in the booking mutation.

Use a delivery claim so concurrent runs cannot send the same row. Record sent time, attempt state and a stable message identifier. Retry definite transient failures while the turn is eligible. Missing contact and delivery failures are visible to reception. SMTP acceptance and database commit cannot be atomic. For an ambiguous send outcome (including a crash after dispatch started), mark delivery for review rather than blindly sending a duplicate. Provide a test mailbox for acceptance. Email includes appointment details and local time.

### 5. Clinical records and timeline

Extend `clinical_records` with a consultation (patient, responsible professional, encounter timestamp, reason, initial clinical evolution), append-only progress notes (consultation, author, timestamp, text), and personal/family history entries with immutable revisions (category, relevant family relationship, description, author, timestamp). Bind patient from the authorized chart and professional from the session. For history updates, require the expected revision so competing edits cannot overwrite one another. New and retried clinical submissions use a stable form operation identifier. Attendance and chart access remain independent of consultation creation.

Build a patient-filtered read projection across sources. Retain source identifiers for authorized drill-down. Apply one global ordering before pagination. Prefer a database union of normalized event summaries to fetching each module's first page. Merge only representations of the same source resource identity, preserving genuinely distinct records.

| Source | Clinical date and attribution |
| --- | --- |
| Admission and vital signs | Admission timestamp, professional if recorded, administrative recorder separately |
| Consultation and progress | Encounter or note timestamp and its own responsible clinician |
| Local prescription | Issue time and prescribing professional |
| External observations and medication records | Source clinical timestamp and asserted author from the external record, or order date/requester for imported medication requests |
| Imported service requests | Source order date and requester, displayed as *Práctica solicitada* |

Order clinical dates descending. Within a date, sort timed records by actual instant, followed by date-only records. Break ties by source type and stable source identifier. Put undated items last and show missing values explicitly. Normalize offsets for sorting, preserve date-only precision on display, and keep ingestion time separate. Patient history revisions are available in their chart section and through audit.

### 6. Clinical audit

Extend `audit` with append-only clinical change events, indexed by patient and event time. Each event carries the patient, source record type and key, operation, actor and/or external origin, timestamp and immutable version references or a minimal field-level change. Instrument the shared write services for admissions, prescriptions, external records/orders, consultations, notes and history revisions. Add the event in the same transaction as the successful clinical write, including bulk import paths. A source identity and revision/operation key provides durable deduplication. Replayed imports and rejected writes produce no additional change event. Scheduling events stay in the appointment's operational history.

Protect reads at query and detail level. The audit workspace supports patient, date and record-type filters and has read-only application permissions. Do not grant update/delete to application-facing roles. An administrator's audit grant does not grant clinical authoring.

## Risks / Trade-offs

- A cached search can outlive the last free slot. Recheck on save and exercise overlapping writes using independent PostgreSQL connections.
- An existing detail view may assume administrative or prescribing privileges. Authorize chart-scoped details independently and verify revocation on the next request.
- Misinterpreting an imported date or author can change the apparent clinical sequence. Test date-only values, missing attribution, interleaved imports and pagination ties using distinct patients.
- Reminder delivery depends on a working mail transport. Exercise the command, scheduling process and test inbox together, including transport failure and reprogramming.

## Migration Plan

Introduce groups, permissions, tables, indexes, constraints and the required PostgreSQL extension through migrations. Check extension creation in the project database before enabling booking. Existing patients, schedules' reference data and source clinical records are read in place. Audit starts with writes made after deployment. Enable navigation after the new tables and services are available, and start the reminder scheduler after email configuration. To back out, stop the scheduler and withdraw the new entry points before reverting application code. Use a disposable local database for destructive migration rehearsals.

## Acceptance evidence

Use the scenarios in the three capability specs and the [story plan](../../../../docs/plan-epica-3-turnos-hce.md). Run signed-out Chromium journeys from `/` using supported provisioning, least-privileged roles and visible patient identifiers. Record the destination, persisted results, executed and skipped counts and service blockers. Distinguish isolated PostgreSQL test-server evidence from running development/Compose evidence. Exercise concurrency with independent sessions and reminder delivery at a controlled clock with a receiving mailbox.
