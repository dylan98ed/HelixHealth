## Purpose

Authorized reviewers can reconstruct changes to a patient's chart across its clinical and interoperability sources.

## ADDED Requirements

### Requirement: Atomic clinical change history (HU-23)

Each successful chart-producing write SHALL record a durable audit event linked to its patient, source record, operation, event time, actor or external origin and the values or immutable versions needed to reconstruct the change.

#### Scenario: Trace local and imported events

- **WHEN** a consultation is saved, an antecedent is corrected, an admission and prescription are recorded and an external order is imported
- **THEN** each change can be traced to its source. A reviewer can identify the old and new antecedent value, the responsible actor and time.

#### Scenario: Rollback and replay

- **WHEN** a write fails before commit or an already recorded clinical operation or import is replayed
- **THEN** the failed write leaves neither a clinical change nor an audit event, and a replay creates no duplicate event.

### Requirement: Read-only, scoped audit access (HU-23)

The audit view SHALL support filters by patient, date and record type for expressly authorized readers. Clinical professionals SHALL additionally require an active treating relationship to the selected patient.

#### Scenario: Administrative and clinical review

- **WHEN** an administrative auditor filters by patient and a professional auditor opens an assigned patient's history
- **THEN** both can read the corresponding events. The application offers neither actor an operation to alter or delete an audit event.

#### Scenario: Ordinary or out-of-scope reader

- **WHEN** reception, a physician without audit permission, or a professional auditor outside the care team requests audit data directly
- **THEN** the service denies the requested data. Revoking a relationship takes effect on the professional's next request.
