from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError

from access_control.actors import ActorContext, ActorRole
from access_control.policies import MissingActorError
from access_control.roles import ADMINISTRATIVE_GROUP, MEDICAL_PROFESSIONAL_GROUP
from professionals.models import HospitalService, Professional, Specialty
from professionals.services import (
    ConfirmationRequiredError,
    ProfessionalConflictError,
    deactivate_professional,
    reactivate_professional,
    register_professional,
    update_professional,
)


@pytest.fixture
def admin_actor(db):
    user = get_user_model().objects.create_user(username="admin", password="x")
    user.groups.add(Group.objects.get(name=ADMINISTRATIVE_GROUP))
    return ActorContext(user.pk, frozenset({ActorRole.ADMINISTRATIVE}))


@pytest.fixture
def references(db):
    return (
        Specialty.objects.create(code="general", name="General"),
        HospitalService.objects.create(code="ward", name="Ward"),
    )


def register(actor, username="subject", dni="01234567"):
    return register_professional(
        actor=actor,
        username=username,
        dni=dni,
        first_name=" Ada ",
        last_name=" Lovelace ",
        date_of_birth=date(1990, 1, 1),
        specialty_code="general",
        hospital_service_code="ward",
    )


@pytest.mark.django_db
def test_registers_known_active_account_and_adds_medical_role(admin_actor, references):
    user = get_user_model().objects.create_user(username="subject", password="x")
    professional = register(admin_actor)
    assert professional.user_id == user.pk and professional.is_registration_complete
    assert (
        professional.first_name == "Ada"
        and professional.registration_number.startswith("PR-")
    )
    assert user.groups.filter(name=MEDICAL_PROFESSIONAL_GROUP).exists()


@pytest.mark.django_db
def test_register_rejects_invalid_or_disabled_account_without_profile(
    admin_actor, references
):
    with pytest.raises(ValidationError):
        register(admin_actor, "unknown")
    assert Professional.objects.count() == 0
    get_user_model().objects.create_user(
        username="disabled", password="x", is_active=False
    )
    with pytest.raises(ValidationError):
        register(admin_actor, "disabled")
    assert Professional.objects.count() == 0


@pytest.mark.django_db
def test_register_completes_legacy_in_place_and_preserves_inactive(
    admin_actor, references
):
    user = get_user_model().objects.create_user(username="subject", password="x")
    legacy = Professional.objects.create(user=user, is_active=False)
    completed = register(admin_actor)
    assert completed.pk == legacy.pk and completed.is_active is False


@pytest.mark.django_db
def test_inactive_legacy_profile_can_reuse_an_active_professionals_dni(
    admin_actor, references
):
    get_user_model().objects.create_user(username="subject", password="x")
    get_user_model().objects.create_user(username="active-subject", password="x")
    active = register(admin_actor, username="active-subject")
    legacy = Professional.objects.create(
        user=get_user_model().objects.get(username="subject"), is_active=False
    )

    completed = register(admin_actor)

    assert completed.pk == legacy.pk and not completed.is_active
    assert completed.dni == active.dni


@pytest.mark.django_db
def test_conflicts_and_lifecycle(admin_actor, references):
    get_user_model().objects.create_user(username="subject", password="x")
    professional = register(admin_actor)
    with pytest.raises(ProfessionalConflictError):
        register(admin_actor)
    with pytest.raises(ConfirmationRequiredError):
        deactivate_professional(
            actor=admin_actor, professional=professional, confirmed=False
        )
    inactive = deactivate_professional(
        actor=admin_actor, professional=professional, confirmed=True
    )
    assert not inactive.is_active
    assert reactivate_professional(
        actor=admin_actor, professional=inactive, confirmed=True
    ).is_active


@pytest.mark.django_db
def test_update_allows_only_mutable_completed_fields(admin_actor, references):
    get_user_model().objects.create_user(username="subject", password="x")
    professional = register(admin_actor)
    changed = update_professional(
        actor=admin_actor, professional=professional, changes={"first_name": " Grace "}
    )
    assert changed.first_name == "Grace" and changed.dni == "01234567"
    with pytest.raises(ValidationError):
        update_professional(
            actor=admin_actor, professional=professional, changes={"dni": "12345678"}
        )


@pytest.mark.django_db
@pytest.mark.parametrize("field", ["first_name", "last_name"])
def test_update_rejects_non_string_names(admin_actor, references, field):
    get_user_model().objects.create_user(username="subject", password="x")
    professional = register(admin_actor)

    with pytest.raises(ValidationError):
        update_professional(
            actor=admin_actor, professional=professional, changes={field: None}
        )

    professional.refresh_from_db()
    assert getattr(professional, field) != "None"


@pytest.mark.django_db
def test_update_replaces_retired_references_and_retains_unchanged_ones(
    admin_actor, references
):
    get_user_model().objects.create_user(username="subject", password="x")
    professional = register(admin_actor)
    retired_specialty, retired_service = references
    retired_specialty.is_active = False
    retired_specialty.save(update_fields=["is_active"])
    retired_service.is_active = False
    retired_service.save(update_fields=["is_active"])
    new_specialty = Specialty.objects.create(code="surgery", name="Surgery")
    new_service = HospitalService.objects.create(code="icu", name="ICU")

    retained = update_professional(
        actor=admin_actor,
        professional=professional,
        changes={
            "last_name": "Byron",
            "specialty_code": retired_specialty.code,
            "hospital_service_code": retired_service.code,
        },
    )
    assert retained.specialty_id == retired_specialty.pk
    assert retained.hospital_service_id == retired_service.pk

    replaced = update_professional(
        actor=admin_actor,
        professional=retained,
        changes={
            "specialty_code": new_specialty.code,
            "hospital_service_code": new_service.code,
        },
    )
    assert replaced.specialty_id == new_specialty.pk
    assert replaced.hospital_service_id == new_service.pk


@pytest.mark.django_db
def test_stale_administrative_actor_loses_authorization_when_group_is_removed(
    admin_actor, references
):
    get_user_model().objects.create_user(username="subject", password="x")
    admin = get_user_model().objects.get(pk=admin_actor.user_id)
    admin.groups.clear()

    with pytest.raises(PermissionDenied):
        register(admin_actor)


@pytest.mark.django_db
def test_wrong_or_inactive_administrative_actor_is_denied(references):
    with pytest.raises(MissingActorError):
        register(None)


@pytest.mark.django_db
def test_reactivation_rechecks_account_references_and_active_dni(
    admin_actor, references
):
    user = get_user_model().objects.create_user(username="subject", password="x")
    professional = register(admin_actor)
    inactive = deactivate_professional(
        actor=admin_actor, professional=professional, confirmed=True
    )
    user.is_active = False
    user.save(update_fields=["is_active"])
    with pytest.raises(ValidationError):
        reactivate_professional(
            actor=admin_actor, professional=inactive, confirmed=True
        )
    user.is_active = True
    user.save(update_fields=["is_active"])
    inactive.specialty.is_active = False
    inactive.specialty.save(update_fields=["is_active"])
    with pytest.raises(ValidationError):
        reactivate_professional(
            actor=admin_actor, professional=inactive, confirmed=True
        )


@pytest.mark.django_db
def test_inactive_completed_profile_can_be_edited_without_reactivation(
    admin_actor, references
):
    get_user_model().objects.create_user(username="subject", password="x")
    professional = deactivate_professional(
        actor=admin_actor, professional=register(admin_actor), confirmed=True
    )
    changed = update_professional(
        actor=admin_actor, professional=professional, changes={"last_name": "Hopper"}
    )
    assert changed.last_name == "Hopper" and not changed.is_active
