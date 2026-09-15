"""DRF representations for the professional lifecycle."""

from collections.abc import Mapping
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from access_control.actors import actor_context_from_user
from access_control.medical_professionals import (
    has_active_medical_professional_context,
)
from professionals.models import Professional
from professionals.services import register_professional, update_professional
from professionals.validators import (
    canonicalize_professional_dni,
    normalize_license_number,
)

PROFESSIONAL_CREATE_FIELDS = (
    "username",
    "dni",
    "license_number",
    "first_name",
    "last_name",
    "date_of_birth",
    "specialty_code",
    "hospital_service_code",
)
PROFESSIONAL_MUTABLE_FIELDS = (
    "license_number",
    "first_name",
    "last_name",
    "date_of_birth",
    "specialty_code",
    "hospital_service_code",
)
PROFESSIONAL_DETAIL_FIELDS = (
    "id",
    "username",
    "dni",
    "license_number",
    "registration_number",
    "first_name",
    "last_name",
    "date_of_birth",
    "specialty_code",
    "hospital_service_code",
    "registration_completed_at",
    "is_active",
    "is_clinically_eligible",
)
IMMUTABLE_PROFESSIONAL_FIELDS = frozenset(
    {
        "id",
        "username",
        "user",
        "user_id",
        "dni",
        "registration_number",
        "registration_completed_at",
        "is_active",
        "is_clinically_eligible",
    }
)


class StrictTextField(serializers.CharField):
    """Reject JSON scalars instead of silently coercing them to text."""

    def to_internal_value(self, data: Any) -> str:
        if not isinstance(data, str):
            raise serializers.ValidationError("Must be provided as text.")
        return super().to_internal_value(data)


class RejectUnknownFieldsMixin:
    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if isinstance(data, Mapping):
            submitted = set(data)
            known = set(self.fields)  # type: ignore[attr-defined]
            invalid = submitted - known
            if invalid:
                errors = {}
                for field_name in sorted(invalid):
                    message = (
                        "This field is immutable."
                        if field_name in IMMUTABLE_PROFESSIONAL_FIELDS
                        else "Unknown field."
                    )
                    errors[field_name] = message
                raise serializers.ValidationError(errors)
        return super().to_internal_value(data)  # type: ignore[misc]


class ProfessionalDetailSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    specialty_code = serializers.CharField(source="specialty.code", read_only=True)
    hospital_service_code = serializers.CharField(
        source="hospital_service.code", read_only=True
    )
    is_clinically_eligible = serializers.SerializerMethodField()

    class Meta:
        model = Professional
        fields = PROFESSIONAL_DETAIL_FIELDS
        read_only_fields = fields

    def get_is_clinically_eligible(self, professional: Professional) -> bool:
        return has_active_medical_professional_context(professional.user)


class ProfessionalSearchResultSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Professional
        fields = ("id", "full_name", "registration_number", "license_number")
        read_only_fields = fields

    def get_full_name(self, professional: Professional) -> str:
        return f"{professional.first_name} {professional.last_name}"


class ProfessionalSearchQuerySerializer(serializers.Serializer):
    dni = serializers.CharField()

    def validate_dni(self, value: str) -> str:
        try:
            return canonicalize_professional_dni(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error


class ProfessionalSearchResponseSerializer(serializers.Serializer):
    results = ProfessionalSearchResultSerializer(many=True)


class ProfessionalCreateSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    username = serializers.CharField(max_length=150)
    dni = serializers.CharField()
    license_number = StrictTextField(
        max_length=50,
        trim_whitespace=False,
    )
    first_name = StrictTextField(max_length=150)
    last_name = StrictTextField(max_length=150)
    date_of_birth = serializers.DateField()
    specialty_code = serializers.CharField(max_length=50)
    hospital_service_code = serializers.CharField(max_length=50)

    def validate_dni(self, value: str) -> str:
        try:
            return canonicalize_professional_dni(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error

    def validate_license_number(self, value: object) -> str:
        try:
            return normalize_license_number(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error

    def create(self, validated_data: dict[str, Any]) -> Professional:
        request = self.context["request"]
        try:
            return register_professional(
                actor=actor_context_from_user(request.user),
                **validated_data,
            )
        except DjangoValidationError as error:
            detail = getattr(
                error, "message_dict", {"non_field_errors": error.messages}
            )
            raise serializers.ValidationError(detail) from error


class ProfessionalUpdateSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    license_number = StrictTextField(
        max_length=50,
        trim_whitespace=False,
        required=False,
        allow_null=False,
        allow_blank=False,
    )
    first_name = StrictTextField(max_length=150, required=False)
    last_name = StrictTextField(max_length=150, required=False)
    date_of_birth = serializers.DateField(required=False)
    specialty_code = serializers.CharField(max_length=50, required=False)
    hospital_service_code = serializers.CharField(max_length=50, required=False)

    def validate_license_number(self, value: object) -> str:
        try:
            return normalize_license_number(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error

    def update(
        self,
        instance: Professional,
        validated_data: dict[str, Any],
    ) -> Professional:
        request = self.context["request"]
        try:
            return update_professional(
                actor=actor_context_from_user(request.user),
                professional=instance,
                changes=validated_data,
            )
        except DjangoValidationError as error:
            detail = getattr(
                error, "message_dict", {"non_field_errors": error.messages}
            )
            raise serializers.ValidationError(detail) from error


class ProfessionalConfirmationSerializer(serializers.Serializer):
    confirm = serializers.BooleanField()
