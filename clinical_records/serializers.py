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
    {"id", "patient", "patient_id", "professional", "professional_id", "created_at"}
)


class AdmissionDetailSerializer(serializers.ModelSerializer):
    patient_id = serializers.IntegerField(read_only=True)
    professional_id = serializers.IntegerField(read_only=True)
    professional_username = serializers.CharField(
        source="professional.user.username",
        read_only=True,
    )

    class Meta:
        model = Admission
        fields = (
            "id",
            "patient_id",
            "professional_id",
            "professional_username",
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
