import json

import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
def test_openapi_endpoints_require_authentication(client, django_user_model):
    endpoint_names = ("api-schema", "api-docs", "api-redoc")

    for endpoint_name in endpoint_names:
        response = client.get(reverse(endpoint_name))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    user = django_user_model.objects.create_user(
        username="schema-reader",
        password="schema-test-password",
    )
    client.force_login(user)

    schema_response = client.get(
        reverse("api-schema"),
        HTTP_ACCEPT="application/json",
    )
    assert schema_response.status_code == status.HTTP_200_OK
    schema = json.loads(schema_response.content)
    assert schema["openapi"].startswith("3.")
    assert schema["info"] == {
        "title": "HelixHealth API",
        "version": "0.1.0",
        "description": "API contracts for the HelixHealth hospital information system.",
    }
    medication_import = schema["paths"]["/catalogs/api/medications/import/"]["post"]
    assert medication_import["operationId"] == "catalogs_medications_import"
    assert (
        medication_import["requestBody"]["content"]["application/json"]["examples"][
            "MedicationIngestionRequest"
        ]["value"]["entries"][0]["code"]
        == "ACET-500"
    )
    assert set(medication_import["responses"]) >= {"200", "400", "409", "413", "415"}

    prescription_issue = schema["paths"][
        "/clinical-records/api/patients/{patient_pk}/prescriptions/"
    ]["post"]
    assert prescription_issue["operationId"] == "prescription_issue"
    assert (
        prescription_issue["requestBody"]["content"]["application/json"]["examples"][
            "PrescriptionIssuanceRequest"
        ]["value"]["items"][0]["duration_days"]
        == 5
    )
    assert (
        "/clinical-records/api/patients/{patient_pk}/prescriptions/{identifier}/report/"
        in schema["paths"]
    )
    assert schema["paths"][
        "/clinical-records/api/patients/{patient_pk}/prescriptions/{identifier}/xml/"
    ]["get"]["responses"]["200"]["content"]["application/fhir+xml"]["schema"] == {
        "type": "string",
        "format": "binary",
    }

    import_issue = schema["paths"][
        "/clinical-records/api/patients/{patient_pk}/exchange/imports/"
    ]["post"]
    assert import_issue["operationId"] == "external_import_issue"
    assert import_issue["responses"]["201"]["content"]["application/json"]["examples"][
        "FHIRImportResult"
    ]["value"]["summary"] == {"record_count": 1}
    assert (
        schema["paths"]["/clinical-records/api/patients/{patient_pk}/exchange/export/"][
            "post"
        ]["responses"]["200"]["content"]["application/fhir+xml"]["schema"]["format"]
        == "binary"
    )

    docs_response = client.get(reverse("api-docs"))
    assert docs_response.status_code == status.HTTP_200_OK
    assert b"SwaggerUIBundle" in docs_response.content

    redoc_response = client.get(reverse("api-redoc"))
    assert redoc_response.status_code == status.HTTP_200_OK
    assert b"redoc.standalone.js" in redoc_response.content
