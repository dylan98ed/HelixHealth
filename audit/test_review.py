from datetime import UTC, datetime
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.urls import reverse

from audit.models import ClinicalAuditEvent
from clinical_records.care_services import (
    assign_care_relationship,
    revoke_care_relationship,
)
from clinical_records.test_care_relationships import care_context as care_context
from patients.models import Patient


def test_review_filters_scope_dates_pagination_and_read_only(care_context, client):
    admin, medical, doctor, patient, coordinator = care_context
    other = Patient.objects.create(
        dni="20831900",
        first_name="Different",
        last_name="Patient",
        date_of_birth=patient.date_of_birth,
    )
    grant = Permission.objects.get(codename="review_chart_audit")
    team, _ = assign_care_relationship(
        actor=coordinator, patient=patient, professional_dni=doctor.dni
    )

    def event(owner, timestamp, source="clinical_records.admission", key="1"):
        with patch("django.utils.timezone.now", return_value=timestamp):
            return ClinicalAuditEvent.objects.create(
                patient=owner,
                actor=admin,
                operation="create",
                source_type=source,
                source_key=key,
                operation_key="initial",
                after={"value": key},
            )

    first = event(patient, datetime(2026, 5, 2, 2, 59, tzinfo=UTC))
    second = event(
        patient, datetime(2026, 5, 2, 3, tzinfo=UTC), "clinical_records.consultation"
    )
    foreign = event(other, datetime(2026, 5, 2, 3, tzinfo=UTC), key="2")
    directory = reverse("audit:review")
    chart = reverse("audit:chart", args=[patient.pk])
    detail = reverse("audit:chart-detail", args=[patient.pk, first.pk])
    assert client.get(directory).status_code == 302
    client.force_login(admin)
    assert client.get(directory).status_code == 403
    admin.user_permissions.add(grant)
    filters = dict(dni=patient.dni, date="2026-05-01", source=first.source_type)
    assert [row[0] for row in client.get(directory, filters).context["rows"]] == [first]
    assert client.get(directory, {**filters, "date": "unknown"}).status_code == 422
    assert not client.get(directory, {**filters, "source": second.source_type}).context[
        "rows"
    ]
    cross = reverse("audit:detail", args=[patient.pk, foreign.pk])
    assert client.get(cross).status_code == 404
    client.force_login(medical)
    assert client.get(chart).status_code == client.get(detail).status_code == 403
    medical.user_permissions.add(grant)
    assert client.get(directory).status_code == 403
    assert client.get(chart).status_code == client.get(detail).status_code == 200
    assert client.get(reverse("audit:chart", args=[other.pk])).status_code == 403
    assert (
        client.get(
            reverse("audit:chart-detail", args=[patient.pk, foreign.pk])
        ).status_code
        == 404
    )
    assert (
        client.post(detail, {"after": "changed"}).status_code
        == client.delete(detail).status_code
        == 405
    )
    first.refresh_from_db()
    assert first.after == {"value": "1"}
    revoke_care_relationship(
        actor=coordinator, patient=patient, relationship=team, confirmed=True
    )
    assert client.get(chart).status_code == client.get(detail).status_code == 403


def test_audit_paging_preserves_filters_and_role_is_required_even_with_grant(
    care_context, client
):
    from html import escape
    from urllib.parse import urlencode

    admin, medical, _, patient, _ = care_context
    admin.user_permissions.add(Permission.objects.get(codename="review_chart_audit"))
    events = [
        ClinicalAuditEvent(
            patient=patient,
            actor=medical,
            operation="create",
            source_type="clinical_records.consultation",
            source_key=str(i),
            operation_key="initial",
            after={"reason": str(i)},
        )
        for i in range(21)
    ]
    ClinicalAuditEvent.objects.bulk_create(events)
    client.force_login(admin)
    url = reverse("audit:review")
    filters = {"dni": patient.dni, "source": events[0].source_type}
    response = client.get(url, filters)
    next_page = "?" + urlencode({**filters, "page": "2"})
    assert f'href="{escape(next_page)}"' in response.content.decode()
    last = client.get(url + next_page).context["rows"]
    assert len(last) == 1 and last[0][0] not in [e for e, _ in response.context["rows"]]
    admin.groups.clear()
    assert client.get(url).status_code == 403
