# Sprint 3 HU-04/HU-05 acceptance guide

These walkthroughs validate professional registration, legacy completion,
maintenance, discovery, and clinical eligibility. Product journeys begin signed
out at `/`. Use an active, non-staff account in the **Administrative** group
unless a different persona is named.

## Register an existing account

1. Choose **Sign in**, authenticate as the application administrator, and open
   **Professionals** from the visible navigation.
2. Choose **Register professional** and supply the username of an existing,
   active login account. The account may have neither a professional profile nor
   the Medical professional role. Account and password creation remain separate
   operator actions; the professional form does not create credentials.
3. Enter a canonical 7- or 8-digit DNI, the required **License number**, names,
   birth date, active specialty, and active hospital service.
4. Submit **Register professional**, then choose **Open professional record**.
   Confirm the entered License number and the separately generated, immutable
   **Registration number** (`PR-...`) are both visible.
5. Sign out and sign in with the newly registered account. It must reach
   **Clinical workspace** and must not gain staff or administrative access.

Repeat the form with a blank License number, an unknown or disabled username,
invalid personal data, a duplicate active DNI/account, or an inactive reference.
The corresponding field must explain the failure, and no partial profile,
medical role, or Registration number may be created.

## Upgrade an incomplete legacy profile

1. Open **Professionals**, choose **Incomplete**, and select the known username.
2. Choose **Complete registration**. The username is fixed. Enter every required
   field, including a real operator-supplied License number, and submit.
3. Choose **Open professional record** and confirm the profile ID, account link,
   and earlier admissions are unchanged. An originally inactive profile remains
   inactive and shows **Reactivate professional**; completion does not activate
   it implicitly.

A medical-role account with no profile or an incomplete profile is deliberately
ineligible. From a fresh sign-in at `/`, it remains on the home page, sees that
professional registration or reactivation is required, and has no **Clinical
workspace** link. Signing in never creates or completes a profile. After an
administrator completes the supported registration workflow, a fresh login can
enter the clinical workspace.

## Maintain and find a completed professional

1. Use **Active**, **Inactive**, or **Incomplete** to discover the appropriate
   state. Each list contains at most 20 records; with 21 or more records, use the
   visible **Next** and **Previous** controls.
2. Choose **Search by DNI**, enter an exact DNI, and submit **Search**. Only an
   active completed professional is returned. Open the saved record with **Open
   professional record**.
3. Confirm **License number** is the external value entered by the operator and
   **Registration number** is the distinct system-generated identifier.
4. Choose **Edit professional** to correct mutable personal data, License
   number, specialty, or hospital service. DNI, account, profile ID, Registration
   number, completion time, activation state, and admission history remain
   unchanged. Clearing a known License number produces a field error.
5. For a completed legacy profile whose License number is NULL, the list and
   detail show **Not recorded**. Open **Edit professional**: leaving that blank
   control untouched preserves the unknown legacy value; entering a value adds
   it. The application never derives it from the Registration number.

## Deactivate and reactivate

1. From an active completed record, choose **Deactivate professional**. Submitting
   without checking the confirmation control shows an error. Check **I confirm
   this change to the professional's status** and submit again.
2. The saved record remains available under **Inactive**, with identity,
   Registration number, and admission history preserved.
3. Choose **Reactivate professional** and explicitly confirm. Reactivation is
   rejected when the account is disabled, a selected specialty or hospital
   service is inactive, or another active professional now owns the DNI.
4. Use **Back to professional** and **Edit professional** to replace retired
   references while the profile remains inactive. Resolve any DNI conflict, then
   repeat the explicit **Reactivate professional** action.

An existing inactive account/profile is not made active by registration or
login. An existing account with no Medical professional role receives that role
only after successful registration. No walkthrough assumes that incomplete
legacy identity data or License numbers were backfilled automatically.

## Automated correspondence

`tests/test_browser_workflows.py` exercises these controls against an isolated
PostgreSQL test server, including JavaScript and non-JavaScript registration,
active/inactive completion, invalid maintenance, search, lifecycle conflicts,
legacy **Not recorded** behavior, 21-record pages, and return to the saved
detail. The disposable Compose runner in
`.agents/skills/validate-live-app/scripts/run_compose_acceptance.py` starts each
journey in a fresh browser context and repeats B1-B4/B8 through the running
application. `verify_acceptance` then checks generated numbers, roles, clinical
eligibility, preserved admissions, lifecycle state, pagination fixtures, and
all fields retained by the existing patient journeys.
