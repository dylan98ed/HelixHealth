## Purpose

Define HU-06 medication prescribing for assigned patients with attributable persisted prescriptions, readable reports, and XML files.

## ADDED Requirements

### Requirement: Discoverable care assignment governs new clinical features
An active non-staff administrator SHALL assign and revoke a professional's care relationship through a patient's Care team screen using a known professional DNI. Assignment SHALL require an active patient and eligible professional; repeated assignment SHALL NOT create duplicate active relationships. Revocation SHALL require confirmation. Patient or professional deactivation SHALL revoke active assignments and reactivation SHALL NOT restore them automatically. New prescription and exchange operations SHALL require an active account, medical role, completed active profile, active patient, and active care relationship; this change SHALL NOT treat a prior admission as assignment.

#### Scenario: Establish the relationship through the product
- **WHEN** an administrator starts signed out at `/`, signs in, finds a patient, follows Care team, looks up an eligible doctor by DNI, and assigns them
- **THEN** one active relationship with actor and time is persisted and the doctor can discover that patient in the assigned-patient view
- **AND** confirmed revocation removes access to the new prescription and exchange surfaces

### Requirement: Issue an attributable medication prescription
An eligible assigned doctor SHALL issue a prescription containing one or more catalog medications, each with positive dose and unit, route, frequency text, positive duration in days, and optional instructions. Patient, prescriber, prescription identifier, issuance time, and clinical snapshots SHALL be server-owned. An optional reason SHALL reference a nomenclature entry. The complete prescription and all items SHALL be saved atomically; issuance SHALL create an immutable record.

#### Scenario: Prescribe catalog medications
- **WHEN** an assigned doctor selects a patient, chooses catalog medication entries, supplies all required directions, and confirms issuance
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
- **WHEN** a doctor starts signed out at `/`, signs in, opens an assigned patient from Clinical workspace, selects Prescriptions then New prescription, corrects an invalid dose, issues the prescription, opens its report, and downloads XML
- **THEN** the final prescription detail, report, and XML describe the same persisted prescription and validation errors did not create extra records

#### Scenario: Access is revoked before an output request
- **WHEN** assignment is revoked or the account, profile, or patient becomes inactive before a report/download request
- **THEN** the request is denied without exposing the saved prescription
