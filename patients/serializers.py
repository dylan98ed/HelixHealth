from collections.abc import Mapping
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from access_control.actors import actor_context_from_user
from patients.forms import PATIENT_MUTABLE_FIELDS, PATIENT_REGISTRATION_FIELDS
from patients.models import Patient
from patients.services import create_patient, update_patient
from patients.validators import validate_patient_dni

PATIENT_DETAIL_FIELDS = (
    "id",
    "dni",
    "clinical_record_number",
    *PATIENT_MUTABLE_FIELDS,
    "is_active",
)
IMMUTABLE_PATIENT_FIELDS = frozenset({"id", "dni", "clinical_record_number"})


class PatientDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = PATIENT_DETAIL_FIELDS
        read_only_fields = PATIENT_DETAIL_FIELDS


class PatientCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = (*PATIENT_REGISTRATION_FIELDS,)
        validators: list[Any] = []
        extra_kwargs = {"dni": {"validators": [validate_patient_dni]}}

    def create(self, validated_data: dict[str, Any]) -> Patient:
        request = self.context["request"]
        actor = actor_context_from_user(request.user)
        return create_patient(actor=actor, **validated_data)


class PatientUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = PATIENT_MUTABLE_FIELDS

    def to_internal_value(self, data: Mapping[str, Any]) -> dict[str, Any]:
        immutable_fields = IMMUTABLE_PATIENT_FIELDS.intersection(data)
        if immutable_fields:
            raise serializers.ValidationError(
                {
                    field_name: "This field is immutable."
                    for field_name in sorted(immutable_fields)
                }
            )
        return super().to_internal_value(data)

    def update(self, instance: Patient, validated_data: dict[str, Any]) -> Patient:
        request = self.context["request"]
        actor = actor_context_from_user(request.user)
        try:
            return update_patient(
                actor=actor,
                patient=instance,
                changes=validated_data,
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict) from error


class PatientDeactivateSerializer(serializers.Serializer):
    confirm = serializers.BooleanField()
