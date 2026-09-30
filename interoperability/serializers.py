"""HTTP representations for bounded external clinical exchange."""

from rest_framework import serializers

from interoperability.limits import MAX_EXPORTED_ADMISSIONS
from interoperability.models import ExternalClinicalRecord, ImportBatch


class ImportRequestSerializer(serializers.Serializer):
    request_key = serializers.UUIDField()
    source_system = serializers.URLField(max_length=500)
    file = serializers.FileField()

    def validate_file(self, value):
        content_type = (getattr(value, "content_type", "") or "").split(";", 1)[0]
        if content_type != "application/fhir+xml":
            raise serializers.ValidationError("Upload an application/fhir+xml file.")
        if value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("FHIR XML files may not exceed 2 MiB.")
        return value


class ExportRequestSerializer(serializers.Serializer):
    admission_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )
    prescription_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list
    )

    def validate(self, attrs):
        admission_ids = attrs["admission_ids"]
        prescription_ids = attrs["prescription_ids"]
        if not admission_ids and not prescription_ids:
            raise serializers.ValidationError("Select at least one clinical record.")
        if len(admission_ids) > MAX_EXPORTED_ADMISSIONS:
            raise serializers.ValidationError(
                f"Select at most {MAX_EXPORTED_ADMISSIONS} admissions per FHIR file."
            )
        if len(set(admission_ids)) != len(admission_ids) or len(
            set(prescription_ids)
        ) != len(prescription_ids):
            raise serializers.ValidationError(
                "Each clinical record may be selected once."
            )
        if admission_ids and prescription_ids:
            raise serializers.ValidationError(
                "Export admissions or one prescription in a separate file."
            )
        if len(prescription_ids) > 1:
            raise serializers.ValidationError("Select one prescription per file.")
        return attrs


class ExternalClinicalRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalClinicalRecord
        fields = (
            "resource_type",
            "external_identifier",
            "kind",
            "source_recorded_at",
            "external_author",
            "content",
        )


class ImportBatchSerializer(serializers.ModelSerializer):
    records = ExternalClinicalRecordSerializer(many=True, read_only=True)
    original_file_url = serializers.SerializerMethodField()

    class Meta:
        model = ImportBatch
        fields = (
            "identifier",
            "received_at",
            "source_system",
            "bundle_identifier",
            "summary",
            "records",
            "original_file_url",
        )

    def get_original_file_url(self, value: ImportBatch) -> str:
        from django.urls import reverse

        return reverse(
            "interoperability:api-import-xml",
            args=[value.patient_id, value.identifier],
        )


class ImportBatchPageSerializer(serializers.Serializer):
    """The stable 20-item history response returned by the import collection."""

    count = serializers.IntegerField(min_value=0)
    next = serializers.IntegerField(required=False, allow_null=True)
    previous = serializers.IntegerField(required=False, allow_null=True)
    results = ImportBatchSerializer(many=True)
