from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, transaction

from clinical_records.care_services import assign_care_relationship
from clinical_records.models import CareRelationship
from clinical_records.test_care_relationships import care_context as _care_context
from patients.models import Patient
from patients.services import deactivate_patient
from professionals.services import deactivate_professional

care_context = _care_context


@pytest.mark.django_db(transaction=True)
def test_assignment_waits_for_patient_deactivation_and_cannot_commit_active(
    care_context,
):
    _, _, professional, patient, actor = care_context
    locked = Event()
    release = Event()

    def deactivate_while_locked():
        close_old_connections()
        try:
            with transaction.atomic():
                Patient.all_objects.select_for_update().get(pk=patient.pk)
                locked.set()
                assert release.wait(15)
                deactivate_patient(actor=actor, patient=patient, confirmed=True)
        finally:
            close_old_connections()

    def try_assign():
        close_old_connections()
        try:
            assert locked.wait(15)
            try:
                assign_care_relationship(
                    actor=actor, patient=patient, professional_dni=professional.dni
                )
            except ValidationError:
                return "denied"
            return "assigned"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        ending = pool.submit(deactivate_while_locked)
        assigning = pool.submit(try_assign)
        assert locked.wait(15)
        release.set()
        ending.result(timeout=20)
        assert assigning.result(timeout=20) == "denied"
    assert not CareRelationship.objects.filter(patient=patient, is_active=True).exists()


@pytest.mark.django_db(transaction=True)
def test_duplicate_assignments_on_separate_connections_have_one_active_pair(
    care_context,
):
    _, _, professional, patient, actor = care_context

    def assign():
        close_old_connections()
        try:
            return assign_care_relationship(
                actor=actor, patient=patient, professional_dni=professional.dni
            )
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: assign(), range(2)))
    assert {item.pk for item, _ in results} == {results[0][0].pk}
    assert sorted(created for _, created in results) == [False, True]
    assert (
        CareRelationship.objects.filter(
            patient=patient, professional=professional, is_active=True
        ).count()
        == 1
    )


@pytest.mark.django_db(transaction=True)
def test_assignment_after_professional_deactivation_cannot_restore_relationship(
    care_context,
):
    _, _, professional, patient, actor = care_context
    locked = Event()
    release = Event()

    def deactivate_while_locked():
        close_old_connections()
        try:
            with transaction.atomic():
                get_user_model().objects.select_for_update().get(
                    pk=professional.user_id
                )
                locked.set()
                assert release.wait(15)
                deactivate_professional(
                    actor=actor, professional=professional, confirmed=True
                )
        finally:
            close_old_connections()

    def try_assign():
        close_old_connections()
        try:
            assert locked.wait(15)
            try:
                assign_care_relationship(
                    actor=actor, patient=patient, professional_dni=professional.dni
                )
            except ValidationError:
                return "denied"
            return "assigned"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        ending = pool.submit(deactivate_while_locked)
        assigning = pool.submit(try_assign)
        assert locked.wait(15)
        release.set()
        ending.result(timeout=20)
        assert assigning.result(timeout=20) == "denied"
    assert not CareRelationship.objects.filter(patient=patient, is_active=True).exists()
