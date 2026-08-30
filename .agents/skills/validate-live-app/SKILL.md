---
name: validate-live-app
description: Validate the real HelixHealth app through PostgreSQL and Chromium after implementation or configuration changes that can affect runtime behavior. Use as the final gate for code-changing tasks; skip explanation, planning, and documentation-only work.
---

# Validate Live App

Validate changed behavior through the running Django application, PostgreSQL, and a real Chromium browser. Treat this as the final implementation gate, not as a replacement for focused tests, linting, typing, or migration checks.

## Workflow

1. Identify the user-visible and integration behavior affected by the task.
2. Run the ordinary focused and project-wide checks appropriate to the change first. Resolve their failures before live validation.
3. Inspect the browser tests marked `browser`. Add or update a focused Playwright scenario when the changed behavior is not already exercised through the UI. Prefer stable roles, labels, and URLs over CSS implementation details.
4. Run the bundled validator from the repository root:

   ```powershell
   uv run python .agents/skills/validate-live-app/scripts/validate_live_app.py
   ```

   The validator starts PostgreSQL only when needed, runs Django's system check, launches the real Django test server through the browser suite, rejects skipped browser scenarios, and stops PostgreSQL only if it started that service.
5. If live validation fails, inspect the application, server, and browser evidence; fix in-scope defects and rerun the relevant scenario followed by the complete browser suite. Do not declare the task complete while an affected workflow is failing.
6. In the final response, state which live workflows were exercised and report the browser-suite result. If validation could not run, state the exact blocker and distinguish it from an application failure.

## Constraints

- Never validate against production or shared clinical data. Use only the repository's local/test environment and generated test records.
- Do not install browsers, start unrelated services, reset databases, or delete volumes without the authorization normally required for those actions.
- A skipped browser test is not successful validation. The bundled validator treats unavailable local Chromium as incomplete validation.
- Preserve services that were already running. Clean up only processes or containers started for this validation.
- For backend-only behavior with no meaningful browser path, exercise the nearest real HTTP/API boundary and explain why browser coverage would add no value.
