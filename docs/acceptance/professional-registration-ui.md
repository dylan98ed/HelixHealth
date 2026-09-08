# Professional registration UI

Sign in from `/` with an active account in the **Administrative** group. Staff
privileges are not required. Choose **Professionals** in the main navigation,
then **Register professional**. Entering no License number produces field feedback
and creates neither the profile nor the medical role.

Use an existing active login username supplied by the account administrator.
If the person has no account, an authorized operator must first create it through
Django Admin's Users interface. The professional form does not create passwords
or staff access. Enter DNI, **License number**, names, birth date, specialty, and
hospital service. License number is the operator-entered credential (for example
`MN 123456`); Registration number is the separate generated internal `PR-`
identifier. New registrations and legacy completion require a nonblank license.
Historical profiles without one show **Not recorded**; Edit professional can add
it, while an untouched blank legacy control preserves the unknown value.
Choose **Register professional**, then **Open professional record**. A successful
registration displays its generated number and grants the account the medical
role. Without JavaScript, submission redirects directly to the saved record.

Errors stay beside the affected fields. Unknown/disabled usernames, invalid
personal details, and retired references cannot create a partial registration.
Duplicate account/DNI errors link to the existing professional record.

For an existing legacy profile, choose **Professionals → Incomplete**, select the
known username, and choose **Complete registration**. The username is fixed;
completion preserves the original profile ID and linked admissions. An inactive
profile stays inactive. From its saved record, **Edit professional** can repair
references while keeping it inactive; **Reactivate professional** requires an
explicit confirmation and an eligible account, active references, and available
DNI. **Deactivate professional** also requires confirmation.

For a completed legacy profile without a recorded license, choose the visible
**Active** or **Inactive** tab and open the profile. Both the directory card and
detail view show **License number: Not recorded** separately from its generated
Registration number. An unrelated Edit professional save keeps the unknown
license; a later edit can add or correct it without replacing the profile,
account, registration timestamp, activation state, or admission history.

The **Active**, **Inactive**, and **Incomplete** tabs have bounded, 20-record
pages. **Search by DNI** finds active registered professionals and offers a
prefilled registration form when no record matches.

This change adds the product UI. The separate API and stricter clinical-access
rollout tasks remain pending in `implement-epics-1-and-2`; existing clinical login
compatibility is retained until that rollout is complete.

Acceptance runs through `tests/test_browser_workflows.py` (signed-out product
navigation, account provisioning through Django Admin, registration with and
without JavaScript, legacy completion and completed-legacy editing, history
preservation, and confirmed reactivation) and the bundled disposable Compose
validator (new registration, fresh medical login, both legacy completion states,
completed active/inactive license edits, and database persistence checks).

## Validation evidence

Validated on 2026-09-08 with the bundled validator: 18 isolated PostgreSQL
Chromium browser tests and 15 disposable Compose Chromium journeys passed, with
zero skipped scenarios. Django checks, migrations, production deployment checks,
and Compose persistence verification also passed.

The affected journeys began signed out at `/` with an active, non-staff
Administrative user. Visible **Professionals** navigation reached Active and
Inactive completed legacy profiles whose License number was NULL while their
account, Registration number, completion timestamp, activation state, medical
group, and admission history already existed. Each journey confirmed **Not
recorded**, saved an unrelated edit without a license, then added and corrected
the License number through **Edit professional**, ending at `/professionals/3/`
and `/professionals/4/` in Compose. Isolated checks compared the
retained profile identity, timestamp, status, permissions, references, and
admissions; Compose persistence verification checked the stored state/history.

The registration journey began signed out at `/` with an active, non-staff
Administrative user. The subject account was created through the supported
Django Admin workflow and initially had no professional profile or medical role.
Visible Professionals → Register professional navigation exercised missing-field
and unknown-account errors, then saved the completed record at `/professionals/7/`
in Compose. PostgreSQL verification confirmed the generated registration number,
medical group, and unchanged non-staff account. A fresh subject login reached
`/clinical-records/`. Isolated tests also exercised the flow without JavaScript
and at a 390-pixel mobile viewport.

The visible Incomplete tab led to active and inactive legacy profiles at
`/professionals/1/` and `/professionals/2/` in Compose. Completion preserved their
IDs and the prior admission relationship; the inactive profile remained inactive.
Isolated browser tests also verified inactive editing and explicit reactivation.
These results belong to isolated test servers and the disposable Compose app;
the user's existing development stack and data were preserved.
