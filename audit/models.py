from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Q

from patients.models import Patient


class ClinicalAuditEvent(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT)
    source_type = models.CharField(max_length=150)
    source_key = models.CharField(max_length=255)
    operation = models.CharField(max_length=64)
    operation_key = models.CharField(max_length=255)
    recorded_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT
    )
    external_origin = models.CharField(max_length=500, blank=True)
    before = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    after = models.JSONField(default=dict, encoder=DjangoJSONEncoder)

    class Meta:
        default_permissions = ()
        indexes = [
            models.Index(
                fields=["patient", "-recorded_at"], name="clinical_audit_patient_time"
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "source_key", "operation_key"],
                name="clinical_audit_source_operation",
            ),
            models.CheckConstraint(
                condition=Q(actor__isnull=False) | ~Q(external_origin=""),
                name="clinical_audit_attributed",
            ),
            models.CheckConstraint(
                condition=~Q(before={}, after={}), name="clinical_audit_has_evidence"
            ),
            models.CheckConstraint(
                condition=~Q(source_type="")
                & ~Q(source_key="")
                & ~Q(operation="")
                & ~Q(operation_key=""),
                name="clinical_audit_identified",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source_type} {self.source_key} · {self.operation}"
