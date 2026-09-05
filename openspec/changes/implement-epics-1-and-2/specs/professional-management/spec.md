## Purpose

Define the observable HU-04 through HU-06 professional lifecycle, educational license verification, care assignment, and audited intervention-note access for the hospital application.

## ADDED Requirements

### Requirement: HU-04 - Register a professional against a known account
An active administrative-role user SHALL be able to register a professional using an existing active login username, DNI, first name, last name, date of birth, license number, specialty, and hospital service. Staff privileges SHALL NOT be required for this product workflow. The system SHALL generate a unique immutable professional registration number and grant the medical role only after successful verification. It SHALL NOT invent credentials, replace the account, or grant staff privileges.

Required names SHALL be trimmed/nonblank, birth date SHALL NOT be future, and assigned specialty/service SHALL be active reference values. DNI SHALL be canonical 7/8 ASCII digits after trimming surrounding form/API whitespace, rejecting internal whitespace/punctuation/Unicode digits.

#### Scenario: New registration succeeds
- **WHEN** an administrator supplies complete valid data and an active matching license for an existing account with no profile
- **THEN** one professional identity and registration number are created, the account receives the medical role, and confirmation links to the saved detail

#### Scenario: No account or invalid fields
- **WHEN** the username does not identify an active account or required professional data is missing/invalid
- **THEN** field errors identify the problem and no professional, credentials, or role assignment is created

#### Scenario: Already completed account
- **WHEN** an administrator attempts registration for an account with a completed professional identity
- **THEN** the system returns an account conflict and offers the existing record instead of creating another identity

#### Scenario: Administrative interfaces cannot bypass registration
- **WHEN** a Django Admin operator inspects professionals or an ordinary application administrator attempts to edit the educational registry
- **THEN** professional add/change/delete actions are unavailable in Django Admin and registry edits require separate operator permissions; verified professional lifecycle changes use the product workflow

### Requirement: HU-04 - Complete legacy identities without losing history
The system SHALL retain existing professional IDs, account links, active flags, and admissions when registration fields are added. It SHALL NOT fabricate missing personal/license data. Administrators SHALL discover incomplete profiles through an Incomplete list and complete them in place. Missing/incomplete profiles SHALL NOT gain clinical access merely through medical role membership after HU-04 rollout.

#### Scenario: Complete an active legacy profile
- **WHEN** an administrator completes and verifies an existing active incomplete profile linked to an admission
- **THEN** the same profile becomes clinically eligible, receives one registration number, and retains the original admission relationship

#### Scenario: Complete an inactive legacy profile
- **WHEN** the same completion workflow succeeds for an inactive profile
- **THEN** its data is completed but it remains inactive, with a separate explicit Reactivate action

#### Scenario: Incomplete professional signs in
- **WHEN** a medical-role account without a completed profile signs in
- **THEN** the application explains that registration/reactivation is required and neither auto-verifies the profile nor grants clinical navigation

### Requirement: HU-04 - Enforce canonical unique identity
The system SHALL permit at most one active professional per canonical DNI. Canonical license numbers SHALL be globally unique, including inactive records. License normalization SHALL trim surrounding whitespace and uppercase ASCII letters, accept 3..32 ASCII characters starting with a letter/digit and continuing with letters/digits/hyphens, and preserve hyphens/leading zeroes. Completed identity values (account, internal ID, DNI, license, registration number) SHALL be immutable.

#### Scenario: Canonical license collision
- **WHEN** MN-001234 is reserved and another registration submits " mn-001234 "
- **THEN** registration is rejected on license_number, even if the original professional is inactive

#### Scenario: Invalid license spelling
- **WHEN** a license contains internal spaces, dots, slashes, non-ASCII characters, or has invalid length
- **THEN** validation rejects it rather than silently deleting characters

#### Scenario: Concurrent identity collision
- **WHEN** two requests compete for the same account, active DNI, or canonical license
- **THEN** at most one registration succeeds and the other receives a field-specific conflict with no partial profile/role change or server error

#### Scenario: Inactive DNI reuse
- **WHEN** an inactive professional's DNI is used for a new account with a different valid license
- **THEN** a distinct active professional can be created; reactivation of the older record is rejected while that active DNI conflict exists

### Requirement: HU-04 - Verify license status and retain outcomes
Registration and reactivation SHALL verify the canonical license against the submitted DNI. The educational source SHALL distinguish active, expired, suspended, not_found, identity_mismatch, and unavailable. An expiry date SHALL remain valid through that date. Unknown entries SHALL NOT be treated as active.

The system SHALL retain each performed verification's subject account, requesting administrator, canonical inputs, outcome, source, and server time, including negative/unavailable outcomes. Only administrators SHALL see this history, with bounded pagination and no edit/delete actions. The UI/docs SHALL clearly label the source educational rather than authoritative real-world licensure.

#### Scenario: Active matching license
- **WHEN** the source confirms matching identity and an active license valid today
- **THEN** registration/reactivation can continue and stores server verification time and expiry

#### Scenario: Negative verification
- **WHEN** the result is expired, suspended, not_found, or identity_mismatch
- **THEN** the operation is rejected with license feedback, activation/group membership is unchanged, and the performed verification remains visible to administrators

#### Scenario: Source unavailable or stale result
- **WHEN** the source cannot answer or its result is over 60 seconds old before activation
- **THEN** the operation returns a visible temporary-unavailability response (API 503) and does not activate or partially complete a profile

#### Scenario: Failed registration has no profile
- **WHEN** verification fails for an otherwise valid new account
- **THEN** no Professional record is created, but an administrator can retrieve the account's verification outcome from the registration interface using its username

### Requirement: Professional maintenance preserves identity and requires explicit activation
Administrators SHALL be able to retrieve profiles and update only names, birth date, specialty, and hospital service on completed profiles, whether active or inactive. Edits SHALL preserve activation state. New reference assignments SHALL be active; unrelated edits MAY retain an unchanged inactive reference. Deactivation SHALL require confirmation, preserve stored identifiers/history, revoke clinical eligibility and active care relationships, and be idempotent. Reactivation SHALL require explicit confirmation, complete data, a fresh active matching license check, active references, and no active-DNI conflict.

#### Scenario: Update mutable data
- **WHEN** an administrator changes valid mutable data
- **THEN** the saved detail shows the changes while account/DNI/license/internal ID/registration number stay unchanged

#### Scenario: Attempt identity or status injection
- **WHEN** a client submits an immutable identifier, license-status/verification field, or unknown writable field to the update API
- **THEN** the system returns field validation errors and does not silently accept the request

#### Scenario: Deactivate and revoke access
- **WHEN** an administrator confirms deactivation
- **THEN** the professional becomes inactive, active care relationships end, and subsequent clinical requests are denied without deleting admissions, interventions, or audits

#### Scenario: Reactivate safely
- **WHEN** an administrator confirms reactivation and all current verification/identity checks succeed
- **THEN** the same identity becomes active, but previously revoked care relationships are not automatically restored

#### Scenario: Unconfirmed or failed reactivation
- **WHEN** confirmation is absent or license/reference/DNI checks fail
- **THEN** the profile remains inactive with actionable feedback and no new relationship

#### Scenario: Repair references before reactivation
- **WHEN** an inactive completed professional has an inactive specialty or service and an administrator selects active replacements through Edit
- **THEN** the references are saved while the profile remains inactive, and a separate confirmed reactivation can proceed through fresh verification

#### Scenario: Renew an expired active profile
- **WHEN** an administrator opens an active profile whose verification has expired
- **THEN** detail explains the visible Deactivate then Reactivate workflow, which refreshes verification without changing identity or restoring old care relationships

### Requirement: HU-05 - Discover and search professional records
The administrative navigation SHALL expose Professionals independently of staff status. The index SHALL provide active-completed, inactive-completed, and incomplete lists, each bounded to 20 rows with visible Next/Previous controls. Exact-DNI search SHALL trim surrounding whitespace, reject other noncanonical characters, and return only the active completed match.

#### Scenario: Matching professional
- **WHEN** an administrator searches an existing active completed professional by DNI
- **THEN** the result shows full name and canonical license with a one-action detail link

#### Scenario: No active match
- **WHEN** the DNI is valid but no active completed professional matches
- **THEN** the result is empty and offers registration with DNI prefilled without creating a profile automatically

#### Scenario: Find an inactive or incomplete profile
- **WHEN** an administrator opens the corresponding visible status tab
- **THEN** the retained profile is discoverable with its detail and appropriate Complete or Reactivate action

#### Scenario: Search response time
- **WHEN** 40 authenticated exact-DNI requests run against 10,000 completed synthetic profiles at the application HTTP boundary
- **THEN** nearest-rank p95 is below two seconds, including authorization and serialization

### Requirement: Professional interfaces have consistent outcomes
Professional HTML and API operations SHALL use the same validation, authorization, verification, and persistence rules. A new API registration SHALL return 201; completion/update/status change 200; field errors 400; identity conflict 409; unavailable verification 503; anonymous/wrong-role API access 403; missing professional 404 after authorization. API search SHALL return a results array with zero or one {id,full_name,license_number}. HTML successes SHALL expose the saved record and failures SHALL preserve submitted values with actionable feedback.

#### Scenario: Product entry journey
- **WHEN** a non-staff administrator starts signed out at /, signs in, and follows Professionals -> Register or a status-list detail action
- **THEN** the workflow is completable without Django Admin or internal identifiers and its outcome matches the persisted state

#### Scenario: Unauthorized professional maintenance
- **WHEN** a requester lacks the administrative role
- **THEN** no professional/verification data or mutation is exposed; anonymous HTML reads go through the application login

### Requirement: HU-06 - Establish and revoke care relationships through the application
Administrators SHALL assign eligible professionals to active patients from the patient's visible Care team interface using a known professional DNI. Assignment SHALL preserve who assigned it and server time; one active relationship per pair is permitted. Revocation SHALL require confirmation and retain history. Admissions SHALL NOT automatically establish care relationships.

#### Scenario: Assign a professional
- **WHEN** an administrator finds a patient through Patient search, opens Care team, and assigns an eligible professional by DNI
- **THEN** one relationship is persisted and the patient appears in that professional's My patients list

#### Scenario: Duplicate assignment
- **WHEN** an active pair is assigned again
- **THEN** the existing relationship is returned without a duplicate

#### Scenario: Invalid assignment
- **WHEN** the patient or professional is inactive/ineligible
- **THEN** the system rejects the assignment without creating a relationship

#### Scenario: Revoke and reassign
- **WHEN** an administrator confirms revocation and later explicitly reassigns the pair
- **THEN** the revoked history remains and a new active relationship is created

### Requirement: HU-06 - Access interventions only for assigned patients
A professional SHALL be permitted intervention access only while the account is active, medical role is present, registration is complete, stored license is active/nonexpired, profile is active, patient is active, and an active care relationship exists. My patients SHALL show only currently accessible patients and provide visible View interventions links. Original authorship or staff/superuser flags alone SHALL NOT bypass these conditions.

#### Scenario: Authorized empty or populated list
- **WHEN** an eligible assigned professional opens View interventions
- **THEN** the system shows the patient's available notes or an explicit empty state, without exposing another patient's data

#### Scenario: Denied patient target
- **WHEN** an authenticated professional requests an unlinked, inactive, or nonexistent patient's interventions
- **THEN** the response is the same generic 403 without note data and the attempt is audited

#### Scenario: Anonymous request
- **WHEN** an anonymous user requests an intervention list
- **THEN** HTML redirects through application login and API returns 403, after retaining a denied audit event with no fabricated actor identity

#### Scenario: Concurrent revocation
- **WHEN** revocation/deactivation commits before a queued clinical operation obtains authorization
- **THEN** that operation is denied even if it previously held a stale active object; an already-authorized operation may complete before revocation commits

### Requirement: HU-06 - Record and correct a minimal intervention note
An eligible assigned professional SHALL be able to record a trimmed nonblank plain-text note of 1..4000 characters. Author, patient linkage, ID, and creation time SHALL be server-controlled. Corrections SHALL append a new same-patient entry linked to the prior entry, require a trimmed 1..500-character correction reason, and preserve all originals. Only the current end of a correction chain can be corrected; admission editing, deletion, diagnoses, and prescriptions are outside this workflow.

#### Scenario: Create from an empty history
- **WHEN** a professional reaches an assigned patient through My patients and submits a valid note
- **THEN** the saved note displays authenticated author and server timestamp, and the corresponding allowed audit is persisted

#### Scenario: Correct an existing note
- **WHEN** an eligible assigned professional follows Correct on the current entry and supplies valid replacement text/reason
- **THEN** a new linked correction is saved, the original text remains retrievable, and the correction audit identifies original and replacement

#### Scenario: Concurrent correction conflict
- **WHEN** two requests try to correct the same current entry
- **THEN** only one successor is stored; the other receives 409 and a conflict audit rather than overwriting or branching history

#### Scenario: Invalid or injected input
- **WHEN** the note/reason is invalid or the client attempts author/patient/time/identity injection
- **THEN** field errors are returned and no clinical entry is created

### Requirement: HU-06 - Bound and escape intervention results
Intervention lists SHALL contain at most 20 entries ordered newest first with deterministic tie-breaking and visible Next/Previous controls. Original notes and corrections SHALL be labeled distinctly. Note/reason text SHALL be escaped as plain text. API list output SHALL use {count,next,previous,results}; entries SHALL contain id,note,author_registration_number,created_at,supersedes_id,correction_reason. Create/correct SHALL return 201; unsupported in-place update/delete SHALL return 405.

#### Scenario: Browse history
- **WHEN** an assigned patient has more than 20 entries and the professional selects Next
- **THEN** older entries appear without dropping authorization, losing original notes, or changing persisted data

#### Scenario: Submitted markup
- **WHEN** stored note text contains HTML/script-like text
- **THEN** it displays literally and does not execute in the browser

### Requirement: HU-06 - Audit consultation and permitted modification attempts
Every intervention-list read, correction-form read, and supported create/correct attempt reaching application dispatch SHALL create exactly one append-only event recording server time, available actor/professional/patient/target identity, attempted target references, action, and allowed/denied/invalid/conflict outcome. Corrections SHALL identify both original target and created replacement. The redirected GET after a POST is a separate read attempt. Transport rejection before domain dispatch (invalid CSRF, malformed HTTP/JSON, unsupported method) is outside clinical-audit coverage.

#### Scenario: Successful consultation or mutation
- **WHEN** an authorized request reads notes or records/corrects one
- **THEN** the event is committed before clinical data is returned; mutation and allowed event succeed together

#### Scenario: Missing identity or target
- **WHEN** the request is anonymous or references an unknown/unauthorized target
- **THEN** the event stores available verified identity and requested references, leaves unknown identities null, and discloses no clinical data to the requester

#### Scenario: Denial survives error response
- **WHEN** authorization, validation, or a correction conflict rejects a dispatched operation
- **THEN** its denied/invalid/conflict event remains persisted after the error response and no partial clinical mutation remains

### Requirement: Audit integrity and availability protect clinical operations
Normal application/API/Admin operations and ordinary database updates/deletes SHALL NOT alter audit events. Audit metadata and routine logs SHALL NOT contain note text, correction prose, DNI, contact data, licenses, credentials, or tokens. Only an explicitly authorized audit operator SHALL inspect events through read-only administration.

#### Scenario: Audit write unavailable
- **WHEN** audit storage fails during a permitted intervention operation
- **THEN** the system returns generic 503 without clinical data, rolls back any mutation, and emits only a content-free operational failure; it does not claim an audit event was recorded

#### Scenario: Attempt to mutate an audit
- **WHEN** normal ORM bulk operations, an application/API action, or ordinary SQL attempts to update/delete an existing event
- **THEN** the mutation is rejected and the original event remains unchanged

#### Scenario: Administrative care privileges are limited
- **WHEN** an application administrator has care-assignment privileges but lacks clinical/audit-reading privileges
- **THEN** those assignment privileges alone do not expose intervention notes or audit content

