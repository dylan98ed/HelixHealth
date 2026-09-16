"""API representations for immutable prescription issuance."""

from django.urls import reverse
from rest_framework import serializers

from prescriptions.models import Prescription, PrescriptionItem


class PrescriptionItemInputSerializer(serializers.Serializer):
    medication_id = serializers.IntegerField(min_value=1)
    dose_value = serializers.DecimalField(max_digits=12, decimal_places=4, min_value=0)
    dose_unit = serializers.CharField(max_length=100)
    route = serializers.CharField(max_length=100)
    frequency = serializers.CharField(max_length=500)
    duration_days = serializers.IntegerField(min_value=1, max_value=365)
    instructions = serializers.CharField(
        max_length=2000, required=False, allow_blank=True
    )

    def validate(self, attrs):
        for field in ("dose_unit", "route", "frequency"):
            if not attrs[field].strip():
                raise serializers.ValidationError(
                    {field: "This field may not be blank."}
                )
        return attrs


class PrescriptionIssueSerializer(serializers.Serializer):
    request_key = serializers.UUIDField()
    reason_entry_id = serializers.IntegerField(
        min_value=1, required=False, allow_null=True
    )
    items = PrescriptionItemInputSerializer(many=True)

    def validate(self, attrs):
        if not 1 <= len(attrs["items"]) <= 50:
            raise serializers.ValidationError(
                {"items": "Provide between 1 and 50 medication items."}
            )
        allowed = {"request_key", "reason_entry_id", "items"}
        unexpected = set(self.initial_data) - allowed
        if unexpected:
            raise serializers.ValidationError(
                {name: "This field is server-owned." for name in unexpected}
            )
        return attrs


class PrescriptionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrescriptionItem
        fields = (
            "sequence",
            "dose_value",
            "dose_unit",
            "route",
            "frequency",
            "duration_days",
            "instructions",
            "snapshot",
        )


class PrescriptionSerializer(serializers.ModelSerializer):
    items = PrescriptionItemSerializer(many=True, read_only=True)
    report_url = serializers.SerializerMethodField()
    xml_url = serializers.SerializerMethodField()

    class Meta:
        model = Prescription
        fields = (
            "identifier",
            "issued_at",
            "snapshot",
            "items",
            "report_url",
            "xml_url",
        )

    def _url(self, value: Prescription, name: str) -> str:
        request = self.context.get("request")
        url = reverse(
            f"prescriptions:{name}", args=[value.patient_id, value.identifier]
        )
        return request.build_absolute_uri(url) if request else url

    def get_report_url(self, value: Prescription) -> str:
        return self._url(value, "report")

    def get_xml_url(self, value: Prescription) -> str:
        return self._url(value, "xml")
