# HelixHealth clinical exchange profile, version 1

HelixHealth exchanges a deliberately small FHIR R4 (4.0.1) XML subset. Files
are self-contained `Bundle.type=collection` resources; this is file exchange,
not a FHIR REST server, document Bundle, terminology server, or regulatory
conformance claim.

The formal, machine-readable constraint inventory is
[`constraints.json`](constraints.json). The checked-in R4 XML schema and the
independent `fhir.resources` model are applied before these local constraints.
The runtime validator uses only checked-in assets and disables DTD/entity and
network resolution. It imposes a 2 MiB file limit, 500 entries, and a maximum
XML depth of 64 at the import boundary (implemented with the importer).

## Deployment identity

`INTEROPERABILITY_BASE_URI`, `INTEROPERABILITY_INSTITUTION_SYSTEM`,
`INTEROPERABILITY_INSTITUTION_CODE`, and `INTEROPERABILITY_INSTITUTION_NAME`
are required outside development and test environments. Development defaults
are synthetic and must not be published as an institutional identity.

The base URI derives these stable systems and profile canonicals:

| Purpose | URI |
| --- | --- |
| Patient DNI | `{base}/identifiers/dni` |
| Professional registration | `{base}/identifiers/professional-registration` |
| Bundle identifier | `{base}/identifiers/bundle` |
| Prescription group | `{base}/identifiers/prescription-group` |
| Profile canonical | `{base}/StructureDefinition/{profile-name}` |

The patient matching contract is the configured DNI identifier plus
`Patient.birthDate`; it never exposes a database primary key. Resources and
entry `fullUrl` values have deterministic UUIDs derived from stable local
identifiers. Every reference is an in-bundle `urn:uuid:` reference.

## Supported resources and semantics

Each bundle contains exactly one Patient, Organization, and Practitioner, then
one or more Observations and/or MedicationRequests. No `entry.request`,
extensions, or resource type outside this list is supported.

Observations must be `final`, categorized as `vital-signs`, and use the
following code/unit pairs:

| Measurement | LOINC code | UCUM unit |
| --- | --- | --- |
| Blood pressure | `85354-9`; components `8480-6`, `8462-4` | `mm[Hg]` |
| Heart rate | `8867-4` | `/min` |
| Temperature | `8310-5` | `Cel` |

Every Observation has Patient subject, Practitioner performer, and the saved
admission timestamp in `effectiveDateTime` and `issued`.

MedicationRequests are `active`/`order`, one per issued item. They retain the
catalog coding including system/version/code/display, Patient subject,
Practitioner requester, issuance timestamp, shared prescription group UUID,
and directions. Dose/unit, route text, frequency text, duration-in-days, and
optional reason coding are represented without inferring a regimen.

Files use the `application/fhir+xml; charset=utf-8` media type and UTF-8 XML.

## Independent fixtures

`fixtures/independent-valid-observation.xml` was authored as a standalone
external example, not produced by the exporter.
`fixtures/invalid-wrong-unit.xml` is its independently authored negative
counterpart. The fixture tests also exercise rejected code, unresolved-reference,
and unsupported-resource variants. Run `uv run pytest
interoperability/test_fhir_export.py -q` to validate the fixtures against the
checked-in schema and the profile implementation.
