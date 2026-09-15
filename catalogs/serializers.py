"""Strict API representations for catalog resources."""

from collections.abc import Mapping

from rest_framework import serializers

from catalogs.models import MedicationEntry, TerminologyEntry


class StrictInputMixin:
    """Reject misspelled fields instead of silently dropping client input."""

    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError(
                {"non_field_errors": ["Expected an object."]}
            )
        unexpected = set(data) - set(self.fields)  # type: ignore[attr-defined]
        if unexpected:
            raise serializers.ValidationError(
                {field: ["This field is not allowed."] for field in sorted(unexpected)}
            )
        return super().to_internal_value(data)  # type: ignore[misc]


class SpecialtySerializer(StrictInputMixin, serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    code = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=100)
    is_active = serializers.BooleanField(default=True)


class TerminologySerializer(StrictInputMixin, serializers.ModelSerializer):
    class Meta:
        model = TerminologyEntry
        fields = (
            "id",
            "system",
            "version",
            "code",
            "display",
            "source_label",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class MedicationSerializer(StrictInputMixin, serializers.ModelSerializer):
    class Meta:
        model = MedicationEntry
        fields = (
            "id",
            "system",
            "version",
            "code",
            "name",
            "presentation",
            "terminology_entry",
            "source_label",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class CatalogImportSerializer(serializers.Serializer):
    source_label = serializers.CharField(max_length=200)
    entries = serializers.ListField(child=serializers.DictField())


class CatalogImportResultSerializer(serializers.Serializer):
    created = serializers.IntegerField(min_value=0)
    unchanged = serializers.IntegerField(min_value=0)
