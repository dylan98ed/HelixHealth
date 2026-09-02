---
name: validate-live-app
description: Validate the real HelixHealth app through PostgreSQL and Chromium after implementation or configuration changes that can affect runtime behavior. Use as the final gate for code-changing tasks; skip explanation, planning, and documentation-only work.
---

# Validate Live App

Validate changed behavior through the running Django application, PostgreSQL, and a real Chromium browser. Live validation must exercise meaningful user workflows and persisted outcomes; proving that a page renders is only a smoke check. Treat this as the final implementation gate, not as a replacement for focused tests, linting, typing, or migration checks.

## Workflow

1. Identify the user-visible and integration behavior affected by the task.
2. Run the ordinary focused and project-wide checks appropriate to the change first. Resolve their failures before live validation.
3. Inspect the browser tests marked `browser`. The baseline suite must authenticate through the UI and exercise representative create workflows, including user creation in Django admin and patient registration. Add or update a focused Playwright scenario when changed behavior is not already exercised through the UI.

   For each affected user-facing workflow, perform a cold-start journey:

   - Start signed out at the normal discoverable entry point, usually `/`.
   - Sign in through the interface intended for that role, using a realistic least-privileged account.
   - Reach the feature through visible navigation and use only identifiers a user would reasonably know. Do not make a hard-coded protected URL or internal database ID the only way the browser test reaches the feature.
   - Verify redirects, denied states, validation feedback, and the resulting persisted state or detail view—not only the HTTP response or page rendering.
   - Keep framework administration distinct from product interfaces. An admin-specific test may use Django Admin; another role's workflow must not use it merely as a convenient authentication shortcut.

   Prefer stable roles, labels, and URLs over CSS implementation details.
4. Run the bundled validator from the repository root:

   ```powershell
   uv run python .agents/skills/validate-live-app/scripts/validate_live_app.py
   ```

   The validator starts PostgreSQL only when needed, runs Django's system check, launches the real Django test server through the browser suite, rejects skipped browser scenarios, and stops PostgreSQL only if it started that service.
5. If live validation fails, inspect the application, server, and browser evidence; fix in-scope defects and rerun the relevant scenario followed by the complete browser suite. Do not declare the task complete while an affected workflow is failing. When validating a user-reported failure, reproduce its exact entry path, session state, account configuration, and actions in a regression scenario before accepting a nearby happy path as evidence.
6. In the final response, state the entry point and user role used for each affected live workflow and report the browser-suite result. If validation could not run, state the exact blocker and distinguish it from an application failure.

## Constraints

- Never validate against production or shared clinical data. Use only the repository's local/test environment and generated test records.
- Do not install browsers, start unrelated services, reset databases, or delete volumes without the authorization normally required for those actions.
- A skipped browser test is not successful validation. The bundled validator treats unavailable local Chromium as incomplete validation.
- A homepage-only smoke test is not sufficient live validation when transactional workflows exist.
- Preserve services that were already running. Clean up only processes or containers started for this validation.
- For backend-only behavior with no meaningful browser path, exercise the nearest real HTTP/API boundary and explain why browser coverage would add no value.
