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
The system SHALL accept DNI values only in the canonical format of 7 or 8 ASCII digits, without punctuation or whitespace, and SHALL NOT allow more than one active patient to have the same DNI.

#### Scenario: Duplicate DNI is rejected
- **WHEN** an administrative user attempts to register a patient whose canonical DNI belongs to an existing active patient
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
The system SHALL allow an administrative user to search for a patient by exact DNI. The system SHALL trim leading and trailing whitespace from search input before validating and matching the DNI; punctuation, internal whitespace, and other noncanonical characters SHALL remain invalid. Under the expected MVP workload, the result SHALL be returned within two seconds and SHALL show the patient's full name and clinical record number.

#### Scenario: Matching patient is found
- **WHEN** an administrative user searches with the DNI of an existing active patient
- **THEN** the system returns the matching full name and clinical record number within two seconds

#### Scenario: No patient matches
- **WHEN** an administrative user searches with a valid DNI that is not registered
- **THEN** the system returns an empty result within two seconds and offers the patient-registration action

#### Scenario: Search input contains surrounding whitespace
- **WHEN** an administrative user searches through the user interface or API with an otherwise valid DNI surrounded by leading or trailing whitespace
- **THEN** the system trims the surrounding whitespace and performs the exact-DNI search using the canonical value

### Requirement: HU-02 - Open patient details from search
The system SHALL allow an administrative user to open the complete patient record with one user action from a matching DNI search result.

#### Scenario: User opens a patient result
- **WHEN** an administrative user selects the matching search result
- **THEN** the system displays that patient's identifiers, demographic data, contact data, address, insurer, and active status

### Requirement: HU-03 - Record consultation reason and vital signs
The system SHALL allow an authorized medical professional to create an admission record for an active patient containing the consultation reason, systolic and diastolic blood pressure, heart rate in beats per minute, and temperature in degrees Celsius.

The system SHALL allow the professional to find the active patient by exact DNI from the medical workflow and open the admission form without entering or knowing the patient's internal identifier.

The system SHALL provide an application-facing clinical workspace, separate from Django administration, where an authenticated active medical professional can see all active patients and start an admission.

#### Scenario: Professional enters the clinical workspace
- **WHEN** an active medical professional signs in through the application login
- **THEN** the system opens the clinical workspace, lists all active patients, excludes inactive patients, and offers an admission action for each listed patient

#### Scenario: Medical-role account has no professional identity yet
- **WHEN** an active user in the Medical Professionals role signs in or returns to the generic landing page without an existing professional identity record
- **THEN** the system provisions the minimal active professional identity and opens the clinical workspace instead of the generic landing page

#### Scenario: Professional enters through the legacy administration login
- **WHEN** an active staff medical professional without administrative permissions signs in through the Django administration login
- **THEN** the system redirects the professional to the clinical workspace instead of displaying an empty administration site

#### Scenario: Authorized administrator enters Django administration
- **WHEN** a staff user with administrative permissions opens the Django administration landing page
- **THEN** the system preserves access to Django administration without redirecting the user to the clinical workspace

#### Scenario: Professional selects a patient for admission
- **WHEN** an authorized medical professional searches with the exact DNI of an active patient
- **THEN** the system shows the patient's full name and clinical record number and offers the admission action in one click

#### Scenario: No active patient is available for admission
- **WHEN** an authorized medical professional searches with a valid DNI that does not belong to an active patient
- **THEN** the system reports that no active patient matches and does not expose an admission action

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

