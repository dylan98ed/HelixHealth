import json

import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
def test_openapi_endpoints_require_authentication(client, django_user_model):
    endpoint_names = ('api-schema', 'api-docs', 'api-redoc')

    for endpoint_name in endpoint_names:
        response = client.get(reverse(endpoint_name))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    user = django_user_model.objects.create_user(
        username='schema-reader',
        password='schema-test-password',
    )
    client.force_login(user)

    schema_response = client.get(
        reverse('api-schema'),
        HTTP_ACCEPT='application/json',
    )
    assert schema_response.status_code == status.HTTP_200_OK
    schema = json.loads(schema_response.content)
    assert schema['openapi'].startswith('3.')
    assert schema['info'] == {
        'title': 'HelixHealth API',
        'version': '0.1.0',
        'description': 'API contracts for the HelixHealth hospital information system.',
    }

    docs_response = client.get(reverse('api-docs'))
    assert docs_response.status_code == status.HTTP_200_OK
    assert b'SwaggerUIBundle' in docs_response.content

    redoc_response = client.get(reverse('api-redoc'))
    assert redoc_response.status_code == status.HTTP_200_OK
    assert b'redoc.standalone.js' in redoc_response.content
