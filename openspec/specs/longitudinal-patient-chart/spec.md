# longitudinal-patient-chart Specification

## Purpose

Treating physicians review and document care in a patient-specific chart assembled from local and imported clinical records.

## Requirements

### Requirement: Chart access through the care team (HU-19)

The system SHALL permit chart access for an eligible medical account with an active care relationship to the patient. It SHALL verify this scope for the patient list, summary, source details and clinical writes.

#### Scenario: Discover an assigned patient

- **WHEN** an operator assigns a patient through the care-team workflow and the physician logs in from the home page
- **THEN** the medical workspace leads to that patient's identified chart, showing history and available clinical entries or an explicit empty state.

#### Scenario: Booking and revocation are independent

- **WHEN** a physician outside the team receives a booking, the patient checks in, and later the operator grants then revokes the care relationship
- **THEN** booking and arrival grant no chart access. Assignment enables access and revocation denies the next read or write even in an open session. Canceling a booking alone preserves an existing care relationship.

#### Scenario: Ineligible clinician

- **WHEN** an account lacks the medical role, has an inactive or incomplete professional profile, or attempts another patient's source detail
- **THEN** the system denies access to the affected chart data.

### Requirement: Document the encounter and progress (HU-20)

The treating physician SHALL be able to save a consultation with reason, initial evolution, visit time, patient and responsible professional, and append separately dated and authored progress notes.

#### Scenario: Consultation after check-in

- **WHEN** the physician opens the assigned patient's chart, saves a consultation and adds a progress note
- **THEN** after re-entry the chart shows both entries in order with their correct authorship. The appointment retains its arrival state.

#### Scenario: Invalid or repeated submission

- **WHEN** required text is empty, a revoked assignment is used, or a valid submission is retried
- **THEN** invalid writes leave no partial record. The successful submission and its retry produce one entry. A supplied author cannot override the authenticated clinician.

### Requirement: Cross-module chronology and provenance (HU-21)

The chart SHALL provide one patient-scoped chronological list of available vital signs, prescriptions, imported observations and orders, consultations and progress, with date, provenance and responsible professional when known. Imported procedure orders SHALL appear as requested procedures (Práctica solicitada).

#### Scenario: Late import interleaved with local care

- **WHEN** an order received today was authored before a local prescription and an admission
- **THEN** the order appears once in clinical-date order, with its requester. Local vitals and prescriptions keep their originating values and authors.

#### Scenario: Pagination, date precision and attribution

- **WHEN** items share a date, a source supplies only a calendar date, or an admission has an administrative recorder alone
- **THEN** paging preserves stable global order without duplicates, displays the recorded precision and identifies the recorder separately. No detail or list entry exposes a second patient's data.

### Requirement: Personal and family history (HU-22)

A treating physician SHALL create, view and update personal and family history in distinct categories, including family relationship where applicable. Updates SHALL preserve prior values and authorship.

#### Scenario: Correct a family history item

- **WHEN** a clinician records both categories, reopens the chart and updates the family entry
- **THEN** the current family entry shows the correction, the personal entry retains its text and the previous family revision is available to authorized audit readers.

#### Scenario: Conflicting or invalid correction

- **WHEN** the form is stale after another edit, the content is empty or the item belongs to a different patient
- **THEN** the current revision remains intact and the attempted change is rejected.
