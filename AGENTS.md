# Repository Agent Instructions

## Development database policy

During the current development phase, this project's local development and test
databases are disposable. Resetting, dropping, and recreating them, including
their project-owned Compose database volumes, is authorized when needed for
development or validation without asking for confirmation again. Verify the
target belongs to this project's local development or test environment first.

Legacy data preservation, backward compatibility with old schemas or account
states, and upgrade paths for existing development data are not requirements
unless the user explicitly requests them. Prefer a clean database when existing
data or schema incompatibilities obstruct a change. Do not add compatibility
code or legacy acceptance scenarios solely to preserve historical development
state.

This policy supersedes conflicting legacy-preservation or database-reset
guidance in existing project plans, acceptance documents, and local skills.
Validation must still exercise the supported current workflows and verify their
persisted results.

## User-facing definition of done

For changes that alter a user-visible workflow, working endpoints and direct
route access are not sufficient evidence of completion.

- Validate the complete journey from a fresh signed-out browser session.
- Start from the normal discoverable entry point, usually `/`, and use only
  visible links, forms, and identifiers that the user would reasonably know.
- Use a realistic least-privileged account for each affected role. Include
  relevant account and domain states supported by current workflows, such as
  missing roles or inactive profiles, when they can change the outcome.
- Verify authentication, redirects, navigation, authorization, validation
  errors, and the final persisted result—not merely page rendering.
- Do not use Django Admin as a substitute for a user-facing interface unless
  the requirement explicitly calls for an administrative workflow.
- Do not treat a workflow as discoverable when the browser test reaches it only
  through a hard-coded protected URL or an internal database identifier.
- When a user reports a failure, add a regression scenario that reproduces the
  exact entry path, session state, account configuration, and actions they used.

Backend-only behavior without a meaningful browser path may be validated at the
nearest real HTTP or integration boundary.

## Browser fixture integrity

- Browser fixtures may create unrelated prerequisite data, but they MUST NOT
  directly create the identity, permission, relationship, or domain state that
  the journey is intended to establish or validate.
- When a workflow is responsible for provisioning or changing state, begin the
  browser scenario without that state, perform the real user-visible workflow,
  and verify that the expected state was persisted.
- Set up accounts through the same supported provisioning path used by a real
  operator or user. An ORM or database shortcut is acceptable only for
  unrelated background data or when the test explicitly targets behavior after
  that state already exists.
- Include realistic partial states that current supported workflows can
  produce. A fully populated factory object is not evidence that those
  workflows can establish the required state. Historical upgrade and legacy
  compatibility scenarios are required only when explicitly requested.

## Completion evidence for user-facing changes

Do not report a user-facing change as complete without stating all of the
following in the final response:

- The browser entry point and whether the session began signed out or already
  authenticated.
- The persona, permissions, and relevant initial account or domain state.
- The visible actions performed and the final URL or visible destination.
- The persisted outcome or other externally observable result.
- The browser-suite result, including executed and skipped test counts.
- Whether validation ran against an isolated test server or the running
  development/Compose application. Do not present one as evidence for the
  other.

If the affected browser journey cannot run, is skipped, or depends on an
unavailable browser or service, report the change as incompletely validated and
name the exact blocker. Do not delegate automatable acceptance testing to the
user.
