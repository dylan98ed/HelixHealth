## Purpose

Define the supplied HU-05 professional registration API and its consistency with the existing administrative registration screens.

## ADDED Requirements

### Requirement: Register a professional through the shared product contract
An active non-staff administrator SHALL register a professional for an existing active username using canonical DNI, first name, last name, date of birth, active specialty, active hospital service, and a required license number. The system SHALL atomically persist the profile, generate a unique immutable registration number, and assign the medical role. It SHALL NOT create credentials or staff privileges. The registration number SHALL remain distinct from the entered license number. Names SHALL be nonblank; birth dates SHALL NOT be future; DNI SHALL contain 7 or 8 ASCII digits after trimming surrounding whitespace.

#### Scenario: New registration through the API
- **WHEN** an administrator submits valid input to `POST /professionals/api/` for an active account with no profile or medical role
- **THEN** the response is 201 with the saved profile, separate license and registration numbers, and a detail link
- **AND** exactly one profile and the medical role are persisted without changing account credentials or staff status

#### Scenario: Failed registration has no side effects
- **WHEN** the account is unknown or disabled, a reference is unavailable, or a required input is invalid
- **THEN** the API returns field errors with status 400 and neither a new profile nor a role assignment is persisted

### Requirement: Professional DNI is unique regardless of activation
The system SHALL reject registration of another professional with the same canonical DNI, including when the existing professional is inactive. Concurrent conflicting registrations SHALL result in one saved identity and a controlled 409 conflict for the other request. Deactivation SHALL NOT free a DNI for reuse. The patient DNI policy SHALL remain unchanged.

#### Scenario: Inactive professional already owns the DNI
- **WHEN** an administrator submits an inactive professional's DNI for another account
- **THEN** registration returns 409 identifying the DNI conflict and the existing professional to the authorized administrator
- **AND** the existing record is available for its supported maintenance workflow

### Requirement: License input remains unverified
License number SHALL remain required trimmed nonblank text of at most 50 characters, preserving meaningful prefixes and leading zeroes. Per the user's explicit instruction, this change SHALL NOT validate credential currency, expiry, status, or external registry membership, and SHALL NOT block prescribing based on such checks or label a license as verified. Omitted license input on an ordinary update SHALL retain the value; explicit blank or null SHALL be rejected.

#### Scenario: Accept an entered license without checking validity
- **WHEN** an administrator enters syntactically valid license text during registration
- **THEN** the text is saved as supplied after trimming, without a validity lookup or expiry requirement
- **AND** API and screen output do not assert that it is current

### Requirement: Consistent professional API and navigation
The system SHALL expose administrative registration, exact-DNI search, detail, partial update, deactivation, and reactivation through the existing planned `/professionals/api/` route family. Identity, username association, registration number, and server timestamps SHALL be read-only; status changes SHALL require an explicit confirmed action. Unsupported PUT/DELETE SHALL return 405, forbidden access 403, missing authorized targets 404, validation failures 400, and identity conflicts 409. API errors SHALL match the underlying rules used by forms. New or incomplete identities SHALL gain clinical eligibility only after successful supported registration; sign-in SHALL NOT create a profile or medical role.

#### Scenario: Register and sign in through visible controls
- **WHEN** a non-staff administrator starts signed out at `/`, signs in, follows Professionals and Register professional, submits invalid then corrected data for an account without a profile or medical role, and opens the saved detail
- **THEN** errors preserve form input and the successful detail displays the persisted separate identifiers
- **AND** exact-DNI search finds that record and a fresh sign-in by the registered doctor reaches Clinical workspace

#### Scenario: No permission through partial identity or injected input
- **WHEN** a no-role account, missing-profile account, incomplete professional, or inactive professional attempts clinical access, or an administrator injects immutable fields in an update
- **THEN** the unsupported access or mutation is rejected without provisioning or changing identity state
