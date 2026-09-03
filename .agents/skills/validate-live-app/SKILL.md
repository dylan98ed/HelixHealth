---
name: validate-live-app
description: Validate the real HelixHealth app through PostgreSQL and Chromium after implementation or configuration changes that can affect runtime behavior. Use as the final gate for code-changing tasks; skip explanation, planning, and documentation-only work.
---

# Validate Live App

Validate changed behavior through the running Django application, PostgreSQL, and a real Chromium browser. Live validation must exercise meaningful user workflows and persisted outcomes; proving that a page renders is only a smoke check. Treat this as the final implementation gate, not as a replacement for focused tests, linting, typing, or migration checks.

## Workflow

1. Identify the user-visible and integration behavior affected by the task.
2. Run the ordinary focused and project-wide checks appropriate to the change first. Resolve their failures before live validation.
3. Inspect the browser tests marked `browser` and the Compose acceptance journeys. The isolated suite must authenticate through the UI and exercise representative create workflows. The Compose journeys must use the seeded personas and must not directly create the identity or relationship being validated. Add or update a focused scenario when changed behavior is not already exercised through the appropriate environment.

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

   The validator performs two distinct gates:

   - It runs the isolated PostgreSQL browser suite and rejects skipped scenarios.
   - It creates a uniquely named disposable Compose project with free host ports and a dedicated PostgreSQL volume, builds the current `web` service, applies migrations, seeds deterministic acceptance personas, drives the real HTTP service through Chromium, and verifies persisted outcomes inside the container.

   The Compose personas cover a Django administrator, an application administrator, medical accounts with active, inactive, missing, and legacy staff profile states, and active/inactive patients. The browser journeys cover identity provisioning, legacy admin redirection, inactive denial, admission creation, patient registration, Django Admin user creation, and read-only clinical-event inspection.

   The validator always targets only its `helixhealth-validation-*` Compose project and removes that project's containers, network, volume, and locally built image afterward. Existing development services and data are not reused or modified. On failure it preserves the browser screenshots, summary, and Compose logs in the reported temporary artifact directory.
5. If live validation fails, inspect the application, server, and browser evidence; fix in-scope defects and rerun the relevant scenario followed by the complete browser suite. Do not declare the task complete while an affected workflow is failing. When validating a user-reported failure, reproduce its exact entry path, session state, account configuration, and actions in a regression scenario before accepting a nearby happy path as evidence.
6. In the final response, state the entry point and user role used for each affected live workflow and report the browser-suite result. If validation could not run, state the exact blocker and distinguish it from an application failure.

## Constraints

- Never validate against production or shared clinical data. Use only the repository's local/test environment and generated test records.
- Do not install browsers, start unrelated services, reset databases, or delete volumes without the authorization normally required for those actions.
- A skipped browser test is not successful validation. The bundled validator treats unavailable local Chromium as incomplete validation.
- A homepage-only smoke test is not sufficient live validation when transactional workflows exist.
- Preserve services that were already running. Clean up only the uniquely named disposable Compose project created for validation.
- For backend-only behavior with no meaningful browser path, exercise the nearest real HTTP/API boundary and explain why browser coverage would add no value.
