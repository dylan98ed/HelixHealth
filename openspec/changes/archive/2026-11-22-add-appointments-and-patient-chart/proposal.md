## Why

Reception needs to offer real openings and keep a reliable daily agenda when several operators book concurrently. Treating physicians need a patient-scoped chart that brings existing records together and preserves the authorship and history of new clinical entries.

## What Changes

- Let reception offer named professional/time pairs, reserve the patient's choice, confirm requests manually, record arrivals and send confirmed-appointment reminders by email.
- Give schedule administrators effective-dated availability controls and give reception a dedicated group with an identity lookup.
- Extend the clinical workspace with consultations, progress notes, personal and family history, a chronological chart and a permission-scoped audit view.
- Deliver the twelve stories in the [agreed implementation plan](../../../../docs/plan-epica-3-turnos-hce.md). Scope exclusions are HU-16 automatic assignment, WhatsApp integration and recording procedure performance or results.

## Capabilities

### New Capabilities

- `appointment-scheduling` covers HU-11–15, HU-17 and HU-18.
- `longitudinal-patient-chart` covers HU-19–22.
- `clinical-change-audit` covers HU-23 and the event contract for chart-producing modules.

### Modified Capabilities

## Impact

The change adds PostgreSQL-backed scheduling, an email delivery process and Django workflows in reception and the medical workspace. It extends access control, clinical records and audit, and integrates admission, prescribing and import write paths. It reuses the existing patient and professional identities, specialty catalog and care-team assignment.
