## Why

The supplied model diagram includes a professional's license number (for example, `MN 123456`), which the application cannot currently store. All illustrated patient fields already exist; the user confirmed that the diagram is a minimum set and that existing fields must remain.

## What Changes

- Document the English model-field mapping for both Patient and Professional, preserving every existing field and relationship.
- Add `Professional.license_number`, displayed as **License number**, for an operator-entered professional license identifier.
- Preserve the generated `registration_number` as a separate internal registration identifier. Never infer a license from a `PR-` number.
- **BREAKING for new registration/completion input:** require a nonblank license number alongside the existing required professional fields. Existing rows migrate with an unknown (`NULL`) license; their IDs, registration timestamps, status, and clinical history remain unchanged.
- Allow administrative users to add or correct a license through the existing professional Edit workflow; display it distinctly in detail, list/search results, and professional API representations as those endpoints are implemented.
- Preserve current patient fields, professional birth date/hospital service, clinical eligibility, role provisioning, and confirmation-based deactivation/reactivation behavior.

## Capabilities

### New Capabilities

- `professional-licensing`: Store, validate, display, and maintain an entered professional license number independently of generated internal identifiers, including safe legacy migration.

### Modified Capabilities

None under `openspec/specs/`, which currently has no published capability specs. This additive capability extends the in-progress `professional-management` contract in `implement-epics-1-and-2`; its existing fields and non-licensing requirements remain in force. The patient diagram requires no patient behavior change.

## Impact

- `professionals/models.py`, additive migration after the current leaf, validators, services, forms, templates, and any professional serializers implemented before this change is applied.
- Registration/completion inputs and detail/search outputs; updates accept the new mutable `license_number` field.
- Professional tests, existing UI/Compose acceptance journeys, persistence verification, and operator documentation.
- Future professional API and clinical-author display work in `implement-epics-1-and-2` must distinguish license numbers from generated registration numbers.
- Planning only in this proposal. No account changes, database migration execution, destructive field removal, new dependency, or external license verification is authorized by this artifact.
