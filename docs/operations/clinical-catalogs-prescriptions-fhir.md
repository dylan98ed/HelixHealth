# Clinical catalogs, prescriptions, and FHIR exchange operations

This guide describes the bounded catalog, prescribing, and clinical-file
exchange workflows delivered by HelixHealth. It is for an application operator
or an authenticated API client. It complements the authenticated OpenAPI
document at `/api/schema/`; obtain a session through the normal sign-in screen
before opening `/api/docs/` or downloading the schema.

This is not a general FHIR REST server, a terminology server, or a regulatory
conformance statement. License validity is deliberately outside this release:
HelixHealth retains the entered license value but does not check its expiry,
status, or registry validity.

## Access and transport

All unsafe API operations use Django session authentication and require the
normal CSRF token. Catalog maintenance requires an active application
administrator (a Django `is_staff` account alone is insufficient). Catalog
reads additionally allow an active medical professional under the shared
clinical access policy. Prescription and exchange operations require the same
active medical-professional context and an active selected patient.

The API returns JSON errors. It rejects malformed input with `400`, conflicts
with `409`, unsupported JSON/media types with `415`, and catalog payloads over
2 MiB with `413`. Authorized but missing or inactive patient-scoped resources
return `404`; unauthorized accounts do not receive clinical content.

## Catalog ingestion

Use one of these append-only JSON endpoints:

| Resource | API route | Required envelope |
| --- | --- | --- |
| Nomenclature | `POST /catalogs/api/terminology/import/` | `source_label`, `entries[].system`, `version`, `code`, `display` |
| Medications | `POST /catalogs/api/medications/import/` | `source_label`, `entries[].system`, `version`, `code`, `name`, `presentation` |

Send `Content-Type: application/json`. Each upload is limited to 500 rows and
2 MiB. The service validates every row before writing: exact repeats return in
`unchanged`, new rows return in `created`, and an invalid or conflicting row
rejects the entire upload without partial rows. A correction is a new source
version, never an update or deletion of a saved entry.

```json
{
  "source_label": "Example medication release",
  "entries": [{
    "system": "https://catalog.example.test/medications",
    "version": "2026-09",
    "code": "ACET-500",
    "name": "Acetaminophen",
    "presentation": "500 mg tablet"
  }]
}
```

An accepted request returns `200` with `{ "created": 1, "unchanged": 0 }`.
The corresponding visible workflow is `/` -> **Catalogs** -> **Medications**
-> **Import JSON**. The isolated B1 browser journey performs this sequence
without JavaScript and verifies its persisted catalog rows.

## Prescription issue and report

An authorized clinician selects an active patient from **Clinical workspace**,
then follows **Prescriptions** -> **New prescription**. The ordinary
no-JavaScript form creates an immutable prescription only after valid
directions for at least one catalog medication are submitted. The same
workflow is available to an API client at:

`POST /clinical-records/api/patients/{patient_pk}/prescriptions/`

```json
{
  "request_key": "7a8c97fe-6a5c-4a3c-94bb-b7495174cd73",
  "reason_entry_id": 12,
  "items": [{
    "medication_id": 34,
    "dose_value": "500",
    "dose_unit": "mg",
    "route": "oral",
    "frequency": "every 8 hours",
    "duration_days": 5,
    "instructions": "Take with water."
  }]
}
```

A new issuance returns `201`; an identical retry with the same request key
returns `200` and the original immutable record. Reusing a key with changed
normalized content returns `409`. The detail response contains `report_url`
and `xml_url`. Those routes return the printable HTML report and the saved
UTF-8 `application/fhir+xml` attachment respectively; neither route creates a
second prescription:

| Output | Product route | API route |
| --- | --- | --- |
| Printable report | `/clinical-records/patients/{patient_pk}/prescriptions/{identifier}/report/` | `/clinical-records/api/patients/{patient_pk}/prescriptions/{identifier}/report/` |
| FHIR XML download | `/clinical-records/patients/{patient_pk}/prescriptions/{identifier}/xml/` | `/clinical-records/api/patients/{patient_pk}/prescriptions/{identifier}/xml/` |

The isolated B2 journey begins signed out at `/`, corrects invalid directions,
issues a multi-item prescription, opens the report, downloads XML, and checks
that precisely one header and its items persisted.

## FHIR R4 file exchange

The supported profile is documented in
[`../interoperability/fhir-r4/README.md`](../interoperability/fhir-r4/README.md)
and its machine-readable local constraints are in `constraints.json`. It
accepts only a self-contained FHIR R4 4.0.1 XML collection Bundle containing
exactly one Patient, Organization, and Practitioner plus supported
Observations and/or MedicationRequests. Input is bounded to 2 MiB, 500 entries,
and XML depth 64. DTDs, entities, remote references, unsupported resource
types, and unsupported extensions are rejected before a write or network call.

For import, navigate from the selected patient to **Interoperability** ->
**Import FHIR XML**, supply `source_system`, and upload an
`application/fhir+xml` file. The API equivalent is:

`POST /clinical-records/api/patients/{patient_pk}/exchange/imports/`

The source system must equal the bundle Organization identifier. The bundle
patient DNI and birth date must exactly match the selected active patient. A
successful import returns `201` with its batch summary; an identical retry
returns `200` with that same batch. An unsafe, unsupported, or wrong-patient
file returns `400` with no batch or external clinical record written. The
protected original XML is available from the batch detail or:

`GET /clinical-records/api/patients/{patient_pk}/exchange/imports/{identifier}/xml/`

The import-detail screen also offers **Retry this import**. It prepopulates the
same request key and declared source system; choose the original XML file again
and submit it to retrieve the existing batch without duplicating clinical data.

To export, select either one or more admission records or one issued
prescription in **Interoperability** -> **Export selected records**. The API
equivalent is:

`POST /clinical-records/api/patients/{patient_pk}/exchange/export/`

with either `{ "admission_ids": [42], "prescription_ids": [] }` or one
`prescription_ids` UUID. The response is an attachment with media type
`application/fhir+xml; charset=utf-8`; export never writes a new admission or
prescription.

B3 establishes an admission through the visible admission form and exports it.
B4 imports an independently authored matching fixture and downloads its
original file. B6 first submits a wrong-patient fixture and verifies the
visible validation error and no persisted import, then submits the matching
fixture. Focused HTTP/integration tests cover unsafe XML and the remaining
parser, authorization, retry, and conflict cases.
