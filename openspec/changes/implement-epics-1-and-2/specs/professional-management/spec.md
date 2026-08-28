## Purpose

Define the observable professional-registration, lookup, assignment, and audited clinical-access behavior required by Epic 2 of the OpenHIS-UNLaM system.

## ADDED Requirements

### Requirement: HU-04 - Register a professional
The system SHALL allow an administrative user to register a professional with DNI, first name, last name, date of birth, license number, specialty, and assigned hospital service. The system SHALL assign an immutable internal identifier and generate a unique professional registration number when registration succeeds.

#### Scenario: Professional registration succeeds
- **WHEN** an administrative user submits all required professional data with unique identity values and an active license
- **THEN** the system creates the professional, assigns an internal identifier, generates a unique registration number, and displays the created record

#### Scenario: Required professional data is missing or invalid
- **WHEN** an administrative user submits a professional without a required value or with an invalid DNI, date, license, specialty, or service
- **THEN** the system rejects the registration, identifies each invalid field, and creates no professional record

### Requirement: HU-04 - Enforce unique DNI and license
The system SHALL accept DNI values only in the canonical format of 7 or 8 ASCII digits, without punctuation or whitespace. The system SHALL normalize license values before comparison and SHALL NOT allow duplicate active DNI values or duplicate license numbers.

#### Scenario: Duplicate professional identity is rejected
- **WHEN** an administrative user submits a DNI or license number already assigned to another professional
- **THEN** the system rejects the registration and identifies the conflicting field

### Requirement: HU-04 - Validate current professional license
The system SHALL verify that a submitted professional license is active at the time of registration or reactivation. If license status cannot be verified, registration SHALL NOT complete and the system SHALL explain that verification is pending or unavailable.

#### Scenario: License is current
- **WHEN** the configured license-status source confirms that the submitted license is active
- **THEN** the system permits registration to continue

#### Scenario: License is expired, suspended, or unverifiable
- **WHEN** the configured license-status source reports a non-active status or cannot provide a result
- **THEN** the system does not activate the professional and records the verification outcome

### Requirement: Professional records support complete maintenance
The system SHALL allow an administrative user to view and update mutable professional data, specialty, and hospital-service assignments. The system SHALL allow a professional record to be deactivated while preserving identifiers and audit history.

#### Scenario: Professional data is updated
- **WHEN** an administrative user submits valid changes to an existing active professional
- **THEN** the system persists the changes without altering the internal identifier or registration number

#### Scenario: Professional record is deactivated
- **WHEN** an administrative user confirms removal of an existing professional
- **THEN** the system marks the professional inactive, blocks new clinical access, and preserves linked records and audit events

### Requirement: HU-05 - Search for a professional by DNI
The system SHALL allow an administrative user to search for a professional by exact DNI. Under the expected MVP workload, the result SHALL be returned within two seconds and SHALL show the professional's full name and license number.

#### Scenario: Matching professional is found
- **WHEN** an administrative user searches with the DNI of an existing active professional
- **THEN** the system returns the matching full name and license number within two seconds

#### Scenario: No professional matches
- **WHEN** an administrative user searches with a valid DNI that is not registered
- **THEN** the system returns an empty result within two seconds and offers the professional-registration action

### Requirement: HU-05 - Open professional details from search
The system SHALL allow an administrative user to open the complete professional record with one user action from a matching DNI search result.

#### Scenario: User opens a professional result
- **WHEN** an administrative user selects the matching search result
- **THEN** the system displays the professional's identifiers, personal data, license status, specialty, service assignment, and active status

### Requirement: HU-06 - Access interventions for assigned patients
The system SHALL allow an authenticated, active medical professional to view interventions for patients with whom the professional has a recorded care relationship. The system SHALL deny access when professional identity, active status, or care relationship cannot be validated.

#### Scenario: Authorized professional views interventions
- **WHEN** an authenticated active professional requests interventions for a patient linked to that professional
- **THEN** the system displays the patient's available intervention list

#### Scenario: Professional access is denied
- **WHEN** the requester is unauthenticated, inactive, or lacks a recorded care relationship with the patient
- **THEN** the system denies access without disclosing intervention data

### Requirement: HU-06 - Audit intervention consultation and modification
The system SHALL create an append-only audit event for every successful or denied intervention consultation and every permitted intervention modification. Each event SHALL contain the server timestamp, professional identifier, patient identifier, attempted action, target intervention when applicable, and outcome.

#### Scenario: Intervention consultation is audited
- **WHEN** a professional attempts to view a patient's interventions
- **THEN** the system records the attempt and its authorization outcome with the server date and time

#### Scenario: Intervention modification is audited
- **WHEN** an authorized professional modifies intervention data
- **THEN** the system records the professional, patient, target intervention, action, outcome, and server date and time without allowing the event to be edited

