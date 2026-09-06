## Purpose

Allow administrators to record and maintain a professional's license number independently of internal registration identifiers, while retaining the existing patient and professional field contracts.

## ADDED Requirements

### Requirement: Model field coverage remains additive
Patient records SHALL retain the English fields `id`, `dni`, `first_name`, `last_name`, `date_of_birth`, `sex`, `phone`, `email`, and `address`. Professional records SHALL expose `id`, `dni`, `license_number`, `first_name`, `last_name`, and `specialty`. These lists SHALL be minimum field sets, not replacement schemas.

Existing patient clinical record numbers, health insurer, active status, and relationships SHALL remain. Existing professional account links, generated registration numbers, birth dates, hospital services, registration timestamps, active status, and relationships SHALL remain. Existing authorization, immutable identity rules, and confirmed deactivation/reactivation behavior SHALL continue to apply.

#### Scenario: Existing fields remain available
- **WHEN** an administrator registers, views, or maintains a patient or professional after this addition
- **THEN** the record supports the respective minimum field set and retains all previously supported fields and relationships
- **AND** the addition does not remove health insurer, professional birth date, or hospital service from their existing workflows

### Requirement: Store an entered professional license number
The system SHALL expose `license_number` with the English label **License number**. It SHALL store an entered text value of 1 to 50 characters after trimming surrounding whitespace. Prefixes, internal spaces, letter case, and leading zeroes SHALL be preserved. `MN 123456` SHALL be accepted. Except for the unchanged unknown legacy edit control described below, empty, whitespace-only, non-text, and overlength submitted values SHALL receive a license-number field error.

The generated internal `registration_number` SHALL remain distinct, retain its existing generation and immutability rules, and SHALL NOT be copied into or presented as `license_number`. This change SHALL NOT impose license-number uniqueness or claim verification against a licensing authority.

#### Scenario: Record the supplied example
- **WHEN** an administrator supplies DNI `27000000`, license number `MN 123456`, first name `María`, last name `González`, specialty General Medicine, and the other existing required registration inputs
- **THEN** the saved professional exposes those values and a separately generated internal registration number
- **AND** the internal ID is assigned by the system rather than accepted from the example's `1`

#### Scenario: Normalize only surrounding whitespace
- **WHEN** the entered license number is `  MN 001234  `
- **THEN** the saved license number is `MN 001234`, preserving the prefix, internal space, and leading zeroes

#### Scenario: Reject invalid submitted license values
- **WHEN** registration or an explicit license update submits a blank, non-text, or more-than-50-character value
- **THEN** the interface identifies `license_number` as invalid and persists no partial profile or role changes

### Requirement: Include licensing in professional registration and maintenance
New professional registration and completion of an incomplete profile SHALL require a valid license number alongside all existing required inputs. Registration SHALL continue to resolve an existing active login account and grant the medical role only after successful persistence.

Administrative users SHALL be able to add or correct `license_number` through the existing Edit professional workflow on active and inactive completed profiles. Omitting the field in a partial update SHALL preserve the stored value, including an unknown legacy value. Adding or correcting it SHALL preserve the professional's ID, DNI, account, internal registration number, registration timestamp, active state, and linked history. An explicitly submitted empty value SHALL NOT clear a known license.

An unchanged empty License number control on a legacy edit form SHALL represent keeping the unknown value, so unrelated edits remain possible. Explicit empty license values in API updates SHALL be rejected; clients SHALL omit the key to retain an unknown value.

#### Scenario: Register without supplying a license
- **WHEN** an administrator submits an otherwise valid new registration without `license_number`
- **THEN** the interface displays a field error and creates neither a professional profile nor a medical-role assignment

#### Scenario: Complete an inactive legacy profile
- **WHEN** an administrator completes an inactive incomplete profile with its license and all existing required data
- **THEN** the same profile becomes complete while remaining inactive and retains its existing admission links

#### Scenario: Correct a license without replacing identity
- **WHEN** an administrator corrects a completed professional's license through Edit professional
- **THEN** the saved record displays the corrected license and retains all immutable identifiers, activation state, and history

#### Scenario: Unrelated update of an unknown legacy license
- **WHEN** a completed legacy profile has no recorded license and an administrator changes another mutable field without submitting a license
- **THEN** the other field is updated and the license remains unknown without altering activation or registration state

### Requirement: Preserve legacy records during the licensing upgrade
Existing profiles SHALL receive an unknown license value represented as `null` to API consumers and **Not recorded** in the UI. The upgrade SHALL NOT fabricate license numbers, substitute generated registration numbers, remove historical fields, reset completion timestamps, deactivate profiles, or change clinical eligibility solely because their license is unknown. Administrators SHALL be able to supply the missing value through existing maintenance or completion workflows appropriate to the profile's current state.

#### Scenario: Upgrade a completed professional with history
- **WHEN** an existing completed profile with a generated registration number and linked admissions is upgraded
- **THEN** its license is unknown and its identifiers, existing fields, completion timestamp, active flag, permissions, and admission relationships remain unchanged

### Requirement: Present licensing consistently across professional interfaces
Professional registration/completion and edit forms SHALL expose License number. Detail and professional list/search results SHALL display the entered license distinctly from the generated registration number; unknown licenses SHALL display **Not recorded**. Professional JSON detail and search representations SHALL include `license_number` as text or `null` alongside their existing fields, and create/completion/update inputs SHALL use the same validation rules when those API endpoints are available.

The existing non-staff administrative path from `/` through Sign in and Professionals SHALL expose these controls. Wrong-role users SHALL gain no professional maintenance access from this addition. Existing patient representations and clinical-author registration-number keys SHALL remain compatible.

#### Scenario: Discover, register, and inspect a licensed professional
- **WHEN** a non-staff administrator starts signed out at `/`, signs in, follows Professionals then Register professional, and supplies a license and all other required inputs
- **THEN** confirmation leads to the saved detail showing separate license and internal registration numbers
- **AND** a subsequent professional DNI search shows the same license and links to that record

#### Scenario: Read an unknown license through an available API
- **WHEN** an authorized client retrieves or searches a legacy professional with no recorded license
- **THEN** the professional response includes `license_number: null` and retains its previously specified fields
