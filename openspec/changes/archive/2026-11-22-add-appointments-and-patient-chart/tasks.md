## 1. Access and scheduling foundation

- [x] 1.1 Add the Reception group, scheduling and audit permissions, workspace links and post-login routing. Provision least-privileged accounts through the supported flow and verify destinations from signed-out sessions, including an account without a role.
- [x] 1.2 Add scheduling models and migrations for rules, exceptions, requests, contacts, appointments and history. Verify interval validity, exclusion of concurrent overlaps, adjacent appointments and request-to-booking uniqueness on PostgreSQL.
- [x] 1.3 Implement facility-local slot generation and schedule management (HU-12). Verify recurring rules, effective dates, closures, invalid overlaps, preserved bookings and the local-day boundary.
- [x] 1.4 Add transactional booking, rescheduling and cancellation services (HU-13). Use independent database connections to verify one winner for an overlap, rejection of stale edits and preservation of the original booking after a failed move.

## 2. Reception workflows

- [x] 2.1 Deliver the named-slot search and reception-scoped patient lookup (HU-14). Verify a reception-only account can reserve the chosen doctor after identity verification and cannot open clinical details.
- [x] 2.2 Deliver the daily agenda (HU-11). Verify text labels for all five states, date/professional filtering, ordering, empty days and canceled bookings after slot reuse.
- [x] 2.3 Add manual request and same-channel confirmation (HU-15). Reopen a request after an unanswered contact and verify operator, time, channel and exactly one linked appointment after a repeated save.
- [x] 2.4 Add arrival, absence and cancellation actions (HU-18). Test pending and confirmed arrivals, identity mismatch, premature absence and a stale cancellation. Check history and the absence of a clinical write at arrival.
- [x] 2.5 Add the periodic reminder command, scheduler process and configurable email transport (HU-17). Use a frozen clock and a receiving mailbox to validate the 24-hour boundary, late confirmation, stale revision, duplicate run, concurrent claim, recovery after a definite failure and visibility of an ambiguous outcome.

## 3. Clinical authorization, authorship and audit writes

- [x] 3.1 Add the immutable clinical audit event model and service (HU-23). Verify clinical change and event commit together or both roll back, and a repeated source operation has one event.
- [x] 3.2 Add the assigned-patient chart entry and shared access check (HU-19). Verify empty and populated charts, direct details, profile eligibility and immediate revocation. Verify booking, cancellation and check-in leave team membership intact.
- [x] 3.3 Add consultations and progress notes (HU-20) using the audit service. From an assigned patient's chart, verify patient, session author, visit time, separate note authorship, single-save retries and failed validation.
- [x] 3.4 Add versioned personal and family history (HU-22). Verify the current display, family relationship, prior revision, concurrent edits and rejection of a cross-patient update.
- [x] 3.5 Instrument existing admission, local prescription, XML and JSON import services for HU-23. Test bulk creation, retry/no-op and forced rollback with source-level patient attribution.

## 4. Timeline and audit review

- [x] 4.1 Build patient-scoped history summaries from local and external records (HU-21). Test clinical-date ordering across sources, date-only and missing data, duplicate resource identities and stable pagination across ties.
- [x] 4.2 Render timeline entries with authorized source details. Verify an imported order is shown once as a requested procedure, an administrative recorder is correctly attributed and another patient's data stays inaccessible.
- [x] 4.3 Deliver the read-only audit view and patient/date/type filters (HU-23). Verify administrative scope, treating professional scope, revocation, role denial and protection from application edits or deletion.

## 5. End-to-end acceptance

[Acceptance results](acceptance.md)

- [x] 5.1 Complete a signed-out Chromium journey through schedule setup, reception contact, slot selection, booking, confirmation, reminder receipt and arrival. Verify the agenda, mailbox and PostgreSQL state; separately cover failed moves, cancellation and absence.
- [x] 5.2 Complete a signed-out clinical journey from actual care-team assignment to consultation, history revision, cross-module timeline and audit. Verify persisted results as different least-privileged users and verify revocation from a previously open session.
- [x] 5.3 Run the applicable repository suites and live validation gate. Report environment, entry point, initial state, visible actions, final destination, persisted evidence and browser counts (executed and skipped). Record isolated test-server and running development/Compose observations separately.
