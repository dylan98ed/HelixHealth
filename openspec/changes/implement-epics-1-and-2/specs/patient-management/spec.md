## Purpose

Define the observable patient-registration, lookup, maintenance, and admission behavior required by Epic 1 of the OpenHIS-UNLaM educational hospital system.

## ADDED Requirements

### Requirement: HU-01 - Register a patient
The system SHALL allow an administrative user to register a patient with DNI, first name, last name, date of birth, sex, phone, email, address, and health insurer. The system SHALL assign an immutable internal identifier and generate a unique clinical record number when registration succeeds.

#### Scenario: Patient registration succeeds
- **WHEN** an administrative user submits all required patient data with a DNI that is not already registered
- **THEN** the system creates the patient, assigns an internal identifier, generates a unique clinical record number, and displays the created record

#### Scenario: Required patient data is missing or invalid
- **WHEN** an administrative user submits a patient without a required value or with an invalid DNI, date, phone, or email format
- **THEN** the system rejects the registration, identifies each invalid field, and creates no patient record

### Requirement: HU-01 - Prevent duplicate patient identity
The system SHALL normalize DNI values before comparison and SHALL NOT allow more than one active patient to have the same DNI.

#### Scenario: Duplicate DNI is rejected
- **WHEN** an administrative user attempts to register a patient whose normalized DNI belongs to an existing active patient
- **THEN** the system rejects the registration and provides a direct way to open the existing patient's record

### Requirement: Patient records support complete maintenance
The system SHALL allow an administrative user to view and update all mutable patient demographic, contact, address, and insurance data. The system SHALL allow a patient record to be deactivated while preserving identifiers and linked clinical information.

#### Scenario: Patient data is updated
- **WHEN** an administrative user submits valid changes to an existing active patient
- **THEN** the system persists the changes without altering the patient's internal identifier or clinical record number

#### Scenario: Patient record is deactivated
- **WHEN** an administrative user confirms removal of an existing patient
- **THEN** the system marks the patient inactive, excludes the patient from default active searches, and preserves all linked admission and clinical data

### Requirement: HU-02 - Search for a patient by DNI
The system SHALL allow an administrative user to search for a patient by exact DNI. Under the expected MVP workload, the result SHALL be returned within two seconds and SHALL show the patient's full name and clinical record number.

#### Scenario: Matching patient is found
- **WHEN** an administrative user searches with the DNI of an existing active patient
- **THEN** the system returns the matching full name and clinical record number within two seconds

#### Scenario: No patient matches
- **WHEN** an administrative user searches with a valid DNI that is not registered
- **THEN** the system returns an empty result within two seconds and offers the patient-registration action

### Requirement: HU-02 - Open patient details from search
The system SHALL allow an administrative user to open the complete patient record with one user action from a matching DNI search result.

#### Scenario: User opens a patient result
- **WHEN** an administrative user selects the matching search result
- **THEN** the system displays that patient's identifiers, demographic data, contact data, address, insurer, and active status

### Requirement: HU-03 - Record consultation reason and vital signs
The system SHALL allow an authorized medical professional to create an admission record for an active patient containing the consultation reason, systolic and diastolic blood pressure, heart rate in beats per minute, and temperature in degrees Celsius.

#### Scenario: Admission record is valid
- **WHEN** an authorized medical professional submits a consultation reason and all required vital-sign values for an active patient
- **THEN** the system creates one admission record linked to that patient

#### Scenario: Admission value is missing or invalid
- **WHEN** an authorized medical professional submits an admission with a missing consultation reason, incomplete blood pressure, or a vital-sign value outside the accepted input range
- **THEN** the system rejects the admission, identifies the invalid value, and creates no partial record

### Requirement: HU-03 - Attribute and timestamp admission records
The system SHALL set the admission date and time from the server clock and SHALL associate the record with the authenticated medical professional who created it. A user SHALL NOT be able to override either value during creation.

#### Scenario: Admission metadata is recorded automatically
- **WHEN** a valid admission record is created
- **THEN** the stored record contains the creation timestamp and the identifier of the authenticated medical professional

