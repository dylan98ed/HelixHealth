from audit.services import record_clinical_change
from interoperability.models import (
    ExternalClinicalRecord,
    ImportedMedicationRequest,
    ImportedServiceRequest,
)


def record_import(
    source: ExternalClinicalRecord | ImportedMedicationRequest | ImportedServiceRequest,
    actor_id: int | None,
) -> None:
    """Identify the version by its external identity and retained content digest."""
    record_clinical_change(
        source=source,
        actor_id=actor_id,
        external_origin=source.source_system,
        operation="import",
        operation_key=source.content_digest,
        after={
            "external_identifier": source.external_identifier,
            "content_digest": source.content_digest,
        },
    )
