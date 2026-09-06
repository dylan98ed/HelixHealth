import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from access_control.roles import ADMINISTRATIVE_GROUP, MEDICAL_PROFESSIONAL_GROUP
from patients.models import Patient
from patients.test_search import create_patient
from professionals.models import Professional


@pytest.fixture
def directory_patients(db):
    target = create_patient()
    target.first_name, target.last_name = "María Elena", "García López"
    target.save()
    create_patient(dni="7654321", is_active=False)
    create_patient(dni="87654321")
    return target


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("route", "group"),
    [
        ("patients:search", ADMINISTRATIVE_GROUP),
        ("clinical_records:dashboard", MEDICAL_PROFESSIONAL_GROUP),
    ],
)
def test_name_directory_filters_at_authorized_http_boundary(
    client, user_factory, directory_patients, route, group
):
    user = user_factory()
    user.groups.add(Group.objects.get(name=group))
    if group == MEDICAL_PROFESSIONAL_GROUP:
        Professional.objects.create(user=user)
    client.force_login(user)
    for query in ("maría", "GARCÍA", "  López   María ", "Elena García"):
        response = client.get(
            reverse(route),
            {"q": query},
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="patient-directory",
        )
        assert response.status_code == 200
        assert response["Cache-Control"] == "no-store"
        assert list(response.context["active_patients"]) == [directory_patients]
        assert b"<html" not in response.content
        assert b"7654321" not in response.content
    for query in ("nothing matches", "<script>alert(1)</script>", "x" * 151):
        response = client.get(reverse(route), {"q": query})
        assert response.status_code == 200
        assert len(response.context["active_patients"]) == 0
        assert b"<script>alert(1)</script>" not in response.content


@pytest.mark.django_db
def test_directory_pagination_preserves_filter_and_empty_query_resets(
    client, user_factory
):
    user = user_factory()
    user.groups.add(Group.objects.get(name=ADMINISTRATIVE_GROUP))
    client.force_login(user)
    for offset in range(21):
        create_patient(dni=str(30000000 + offset))
    other = create_patient(dni="98765432")
    other.last_name = "Different"
    other.save()
    url = reverse("patients:search")
    first = client.get(url, {"q": "patient"})
    assert len(first.context["active_patients"]) == 20
    assert b"?page=2&amp;q=patient" in first.content
    second = client.get(url, {"q": "patient", "page": 2})
    assert len(second.context["active_patients"]) == 1
    assert first.context["active_patients"][0] != second.context["active_patients"][0]
    cleared = client.get(url, {"q": "  "})
    assert cleared.context["active_patients_page"].paginator.count == 22
    assert Patient.objects.count() == 22


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["patients:search", "clinical_records:dashboard"])
def test_directory_does_not_disclose_to_anonymous_or_wrong_role(
    client, user_factory, directory_patients, route
):
    url = reverse(route)
    anonymous = client.get(url, {"q": "María"}, HTTP_HX_REQUEST="true")
    assert anonymous.status_code == 302
    user = user_factory()
    client.force_login(user)
    denied = client.get(url, {"q": "María"}, HTTP_HX_REQUEST="true")
    assert denied.status_code == 403
    assert directory_patients.dni.encode() not in denied.content


@pytest.mark.django_db
def test_inactive_professional_cannot_query_directory(
    client, user_factory, directory_patients
):
    user = user_factory()
    user.groups.add(Group.objects.get(name=MEDICAL_PROFESSIONAL_GROUP))
    Professional.objects.create(user=user, is_active=False)
    client.force_login(user)
    response = client.get(reverse("clinical_records:dashboard"), {"q": "María"})
    assert response.status_code == 403
    assert directory_patients.dni.encode() not in response.content
