from collections.abc import Mapping
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from access_control.actors import actor_context_from_user
from clinical_records.forms import ADMISSION_INPUT_FIELDS
from clinical_records.models import Admission
from clinical_records.services import InactivePatientError, create_admission
from clinical_records.vital_signs import validate_vital_signs

SERVER_OWNED_ADMISSION_FIELDS = frozenset(
    {
        "id",
        "patient",
        "patient_id",
        "professional",
        "professional_id",
        "recorded_by",
        "recorded_by_id",
        "recorded_by_username",
        "created_at",
    }
)


class AdmissionDetailSerializer(serializers.ModelSerializer):
    patient_id = serializers.IntegerField(read_only=True)
    professional_id = serializers.IntegerField(read_only=True, allow_null=True)
    professional_username = serializers.SerializerMethodField()
    recorded_by_username = serializers.SerializerMethodField()

    def get_professional_username(self, obj: Admission) -> str | None:
        return obj.professional.user.username if obj.professional else None

    def get_recorded_by_username(self, obj: Admission) -> str | None:
        return obj.recorded_by.username if obj.recorded_by else None

    class Meta:
        model = Admission
        fields = (
            "id",
            "patient_id",
            "professional_id",
            "professional_username",
            "recorded_by_username",
            *ADMISSION_INPUT_FIELDS,
            "created_at",
        )
        read_only_fields = fields


class AdmissionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Admission
        fields = ADMISSION_INPUT_FIELDS

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if isinstance(data, Mapping):
            submitted_server_fields = SERVER_OWNED_ADMISSION_FIELDS.intersection(data)
            if submitted_server_fields:
                raise serializers.ValidationError(
                    {
                        field_name: "This field is set by the server."
                        for field_name in sorted(submitted_server_fields)
                    }
                )
        return super().to_internal_value(data)

    def validate(self, attributes: dict[str, Any]) -> dict[str, Any]:
        try:
            validate_vital_signs(attributes)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict) from error
        return attributes

    def create(self, validated_data: dict[str, Any]) -> Admission:
        request = self.context["request"]
        patient = self.context["patient"]
        try:
            return create_admission(
                actor=actor_context_from_user(request.user),
                patient=patient,
                **validated_data,
            )
        except InactivePatientError as error:
            raise serializers.ValidationError({"patient": [str(error)]}) from error
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict) from error
