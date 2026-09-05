## Purpose

Define the observable patient-registration, lookup, maintenance, and admission behavior for HU-01 through HU-03, including preservation of existing clinical records and integration with verified professional identity.

## ADDED Requirements

### Requirement: HU-01 - Register a patient
The system SHALL allow an active administrative-role user, without requiring staff privileges, to register DNI, first name, last name, date of birth, sex, phone, email, address, and health insurer. All fields are required. The system SHALL generate an immutable internal ID and unique clinical record number.

DNI SHALL be stored as 7 or 8 ASCII digits. Form/API boundaries SHALL trim surrounding textual whitespace before canonical validation; punctuation, internal DNI whitespace, and non-ASCII digits remain invalid. Names/sex/address/insurer SHALL be nonblank; birth date SHALL NOT be future; email SHALL have valid email syntax. Phone SHALL contain 7..15 ASCII digits and only digits, spaces, parentheses, hyphens, and an optional leading plus sign.

#### Scenario: Complete registration
- **WHEN** an administrative user submits valid fields with no active patient sharing the canonical DNI
- **THEN** one patient is persisted and the confirmation displays the generated clinical record number with a link to patient detail

#### Scenario: Invalid registration
- **WHEN** required fields are missing or invalid
- **THEN** the bound form/API response identifies the fields, preserves valid submitted values, and creates no patient

### Requirement: HU-01 - Prevent duplicate patient identity
The system SHALL permit at most one active patient per canonical DNI and SHALL preserve this rule under concurrent registration. Inactive records SHALL retain their original identity/history; registering the same DNI again SHALL create a distinct record rather than reactivate or overwrite the inactive one.

#### Scenario: Duplicate active DNI
- **WHEN** an administrator submits a DNI belonging to an active patient
- **THEN** registration is rejected with an existing-record link; the API returns 409 and existing_patient_id

#### Scenario: Concurrent registration
- **WHEN** two valid requests compete for the same active DNI, including a competing insert after initial validation begins
- **THEN** exactly one patient is created and the losing request receives the duplicate conflict instead of a server error

#### Scenario: Reuse an inactive DNI
- **WHEN** only an inactive patient has the submitted DNI and registration succeeds
- **THEN** the new patient has a different ID/clinical record number, and the old patient's admissions and identifiers remain attached to the old record

### Requirement: Patient records support complete maintenance
The system SHALL permit an administrator to view all retained patient details and update names, birth date, sex, contact, address, and insurer on an active patient. Internal ID, DNI, and clinical record number SHALL remain immutable. Deactivation SHALL require explicit confirmation, preserve linked information, and exclude the patient from default active searches. No patient-reactivation workflow is introduced here.

#### Scenario: Update mutable data
- **WHEN** an administrator saves valid changes through patient detail and Edit patient
- **THEN** the changes persist, identifiers stay unchanged, and the application returns to patient detail

#### Scenario: Unconfirmed removal
- **WHEN** the administrator submits deactivation without confirming
- **THEN** the system displays a confirmation-required error and leaves the patient active

#### Scenario: Confirmed deactivation
- **WHEN** the administrator confirms deactivation
- **THEN** detail displays Inactive, edit/deactivate actions disappear, and the original record/admissions remain stored

#### Scenario: Concurrent deactivation and write
- **WHEN** deactivation commits before an overlapping update or admission obtains permission to write, even if that request holds an earlier active patient object
- **THEN** the later operation is rejected without mutation; already-committed clinical history is preserved

### Requirement: HU-02 - Search for a patient by DNI
The system SHALL perform exact active-patient DNI lookup after trimming surrounding whitespace. It SHALL reject punctuation/internal whitespace/noncanonical characters. Search results SHALL show full name and clinical record number, with one action to open detail. An unmatched valid DNI SHALL offer registration prefilled with that DNI without creating a patient automatically.

#### Scenario: Matching patient
- **WHEN** an administrator searches with an active patient's DNI, with or without surrounding whitespace
- **THEN** the same single patient result and detail link are shown

#### Scenario: Missing or inactive match
- **WHEN** no active patient has the valid submitted DNI
- **THEN** results are empty and the prefilled registration action is offered

#### Scenario: Invalid search
- **WHEN** the input is punctuated, contains internal whitespace, or has the wrong digit format
- **THEN** field feedback is shown and no fuzzy/partial search is performed

#### Scenario: Search response target
- **WHEN** 40 authenticated exact-DNI requests are measured against the documented 10,000-patient MVP dataset at the application HTTP boundary
- **THEN** nearest-rank p95 response time is below two seconds, including authorization and serialization

### Requirement: Patient workflows are discoverable and role protected
An administrator SHALL be able to start signed out at /, sign in through the application, reach Patient search, and register/view/edit/deactivate through visible links. Product workflows SHALL NOT require Django Admin or knowledge of internal database IDs. An authenticated user without the administrative role SHALL NOT gain patient-maintenance access.

#### Scenario: Administrative journey
- **WHEN** a non-staff administrative user signs in from the home page
- **THEN** Patient search is reachable and its visible actions lead through registration and maintenance to the saved patient detail

#### Scenario: Unauthorized maintenance
- **WHEN** an anonymous or wrong-role user attempts patient maintenance
- **THEN** anonymous HTML access redirects through application login, API/wrong-role access is denied, and no patient state changes

### Requirement: HU-03 - Discover active patients with bounded lists
An eligible medical professional SHALL reach the clinical workspace through the application. The workspace SHALL provide access to all active patients across pages of at most 20, with visible Next/Previous controls, stable surname/name/ID ordering, and exact-DNI search independent of the current page. Inactive patients SHALL NOT be offered for admission.

#### Scenario: Browse another page
- **WHEN** more than 20 active patients exist and the professional selects Next
- **THEN** the next bounded page appears, Previous permits returning, and pagination alone does not trigger a missing-DNI validation error

#### Scenario: Select by known DNI
- **WHEN** a professional searches the exact DNI of an active patient absent from the current page
- **THEN** the system shows that patient's full name and clinical record number with a one-click admission action

#### Scenario: No active admission target
- **WHEN** a professional searches an inactive/missing DNI or requests an inactive patient's admission URL
- **THEN** no admission action or inactive patient's clinical data is exposed; direct inactive-target UI/API lookup returns 404

### Requirement: HU-03 - Record consultation reason and vital signs
The system SHALL permit an eligible professional to create an admission for an active patient using a nonblank consultation reason, systolic/diastolic pressure, heart rate, and temperature. Default inclusive validation bounds SHALL be systolic 70..250 mmHg, diastolic 40..150 mmHg, heart rate 30..220 bpm, and temperature 30.0..45.0 degrees Celsius with one decimal place. Bounds/units SHALL remain configurable; these are application validation bounds, not treatment guidance.

#### Scenario: Valid admission
- **WHEN** the professional submits all required values within configured bounds
- **THEN** one complete admission is persisted and the saved values appear in the patient admission history

#### Scenario: Missing or out-of-range input
- **WHEN** a reason/vital sign is missing, nonnumeric where numeric is required, or outside a configured bound
- **THEN** each invalid field is identified and no partial admission is created

### Requirement: HU-03 - Attribute, preserve, and paginate admission history
The system SHALL set author and creation timestamp from authenticated identity and server time. Users SHALL NOT override these metadata or edit/delete persisted admission events. Administrative patient detail and medical admission history SHALL show at most 20 events per page, newest first, with visible pagination.

#### Scenario: Server-owned attribution
- **WHEN** an admission is saved
- **THEN** its stored professional is the authenticated professional and timestamp is server-generated; API metadata override attempts are rejected

#### Scenario: Inspect older history
- **WHEN** a permitted user opens a patient with more than 20 admissions and uses Next
- **THEN** older entries appear with original values, author, and timestamp, without modifying any event

### Requirement: Clinical eligibility follows completed professional registration
After the HU-04 rollout, all medical workflows SHALL require an active account with the medical role, an active completed professional registration, and a stored active nonexpired license verification. Group membership alone SHALL NOT authorize clinical access. Existing profile/admission IDs SHALL survive completion.

#### Scenario: Eligible professional login
- **WHEN** an active, completely registered and license-eligible professional signs in from /
- **THEN** the clinical workspace opens and permitted clinical navigation is visible

#### Scenario: Missing or incomplete profile
- **WHEN** a medical-role user with a missing or incomplete profile signs in or revisits /
- **THEN** the system grants no clinical access and explains that administrative registration/reactivation is required; it does not automatically create an active verified profile

#### Scenario: Inactive or expired profile
- **WHEN** an authenticated medical user has an inactive profile or expired verification
- **THEN** clinical navigation is hidden and direct clinical operations are denied without reactivation or mutation

#### Scenario: Legacy staff entry
- **WHEN** an eligible staff medical professional without administrative permissions signs in through the legacy Django Admin entry
- **THEN** the clinical workspace opens instead of an empty Admin index

#### Scenario: Administrative access is preserved
- **WHEN** a user has administrative privileges independently of an ineligible medical profile
- **THEN** the system retains the user's permitted administrative workflows; staff users with Django administrative permissions can still use Django Admin

