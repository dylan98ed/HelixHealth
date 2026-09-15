## Purpose

Define HU-06 medication prescribing using existing clinical access rules, with attributable persisted prescriptions, readable reports, and XML files.

## ADDED Requirements

### Requirement: Issue an attributable medication prescription
A doctor authorized by the existing clinical access rules SHALL issue a prescription for an active patient containing one or more catalog medications, each with positive dose and unit, route, frequency text, positive duration in days, and optional instructions. This change SHALL reuse existing professional eligibility and patient discovery without requiring a care assignment. Patient, prescriber, prescription identifier, issuance time, and clinical snapshots SHALL be server-owned. An optional reason SHALL reference a nomenclature entry. The complete prescription and all items SHALL be saved atomically; issuance SHALL create an immutable record.

#### Scenario: Prescribe catalog medications
- **WHEN** an authorized doctor selects an active patient from the existing clinical directory, chooses catalog medication entries, supplies all required directions, and confirms issuance
- **THEN** a prescription detail is shown with its identifier, patient, actual prescriber, and saved directions
- **AND** every item belongs to that one persisted prescription

#### Scenario: Invalid medication or spoofed prescriber
- **WHEN** an issuance request has no items, an unknown medication, invalid directions, or a client-supplied prescriber or issue time
- **THEN** field errors are returned and no prescription or item is persisted

### Requirement: Prevent duplicate issuance and preserve issued content
Issuance SHALL accept a request key scoped to the doctor and patient. Repeating the same key and normalized payload SHALL return the original prescription; reusing it with different content SHALL return 409. Later profile or patient edits SHALL NOT change the content of an already issued report or XML file. Issued prescriptions SHALL NOT expose edit or delete operations.

#### Scenario: Retry after a lost response
- **WHEN** the doctor resubmits the same issuance request after a network interruption
- **THEN** the original prescription is returned and the stored prescription count is unchanged

### Requirement: Generate readable and interoperable outputs
Each issued prescription SHALL have a printable HTML report and downloadable FHIR R4 XML representation with the same patient, prescriber, issuance identifier/time, and medication directions. The XML SHALL use the documented exchange profile and one MedicationRequest per medication item. Download and report access SHALL recheck patient-level permission and SHALL NOT publicly expose clinical data. Generating an output SHALL NOT issue another prescription.

#### Scenario: Complete the doctor's journey from sign-in
- **WHEN** a doctor starts signed out at `/`, signs in, opens an active patient from Clinical workspace, selects Prescriptions then New prescription, corrects an invalid dose, issues the prescription, opens its report, and downloads XML
- **THEN** the final prescription detail, report, and XML describe the same persisted prescription and validation errors did not create extra records

#### Scenario: Access is revoked before an output request
- **WHEN** the medical role is removed or the account, profile, or patient becomes inactive before a report/download request
- **THEN** the request is denied without exposing the saved prescription
