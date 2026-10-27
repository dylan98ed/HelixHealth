"""Administrative care-team HTML and API endpoints."""

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from access_control.actors import actor_context_from_user
from access_control.policies import IsAdministrativeActor
from access_control.roles import MEDICAL_PROFESSIONAL_GROUP
from clinical_records.care_services import (
    CareConfirmationRequired,
    assign_care_relationship,
    revoke_care_relationship,
)
from clinical_records.models import CareRelationship
from patients.models import Patient
from patients.views import administrative_required
from professionals.models import Professional
from professionals.validators import canonicalize_professional_dni


class CareAssignmentInput(serializers.Serializer):
    professional_dni = serializers.CharField()

    def validate(self, attrs):
        unknown = set(self.initial_data) - {"professional_dni"}
        if unknown:
            raise serializers.ValidationError(
                {key: ["Unknown field."] for key in unknown}
            )
        return attrs

    def validate_professional_dni(self, value):
        try:
            return canonicalize_professional_dni(value)
        except ValidationError as error:
            raise serializers.ValidationError(error.messages) from error


class CareRevokeInput(serializers.Serializer):
    confirm = serializers.BooleanField(required=True)

    def validate(self, attrs):
        unknown = set(self.initial_data) - {"confirm"}
        if unknown:
            raise serializers.ValidationError(
                {key: ["Unknown field."] for key in unknown}
            )
        return attrs

    def validate_confirm(self, value):
        if not value:
            raise serializers.ValidationError("Confirmation is required.")
        return value


def _data(relationship: CareRelationship) -> dict[str, object]:
    return {
        "id": relationship.pk,
        "patient_id": relationship.patient_id,
        "professional_id": relationship.professional_id,
        "professional_registration_number": relationship.professional.registration_number,
        "is_active": relationship.is_active,
        "assigned_at": relationship.assigned_at.isoformat(),
        "revoked_at": relationship.revoked_at.isoformat()
        if relationship.revoked_at
        else None,
    }


def _assign(actor, patient, raw_dni):
    serializer = CareAssignmentInput(data={"professional_dni": raw_dni})
    if not serializer.is_valid():
        return None, None, serializer.errors["professional_dni"][0]
    try:
        assignment, created = assign_care_relationship(
            actor=actor,
            patient=patient,
            professional_dni=serializer.validated_data["professional_dni"],
        )
    except ValidationError as error:
        return None, None, error.messages[0]
    return assignment, created, None


@administrative_required
@require_http_methods(["GET", "POST"])
def care_team(request: HttpRequest, pk: int) -> HttpResponse:
    patient = get_object_or_404(Patient.all_objects, pk=pk)
    error = None
    professional_dni = (
        request.POST.get("professional_dni", "")
        if request.method == "POST"
        else request.GET.get("professional_dni", "")
    )
    matched_professional = None
    if request.method == "GET" and professional_dni:
        lookup = CareAssignmentInput(data={"professional_dni": professional_dni})
        if lookup.is_valid():
            matched_professional = Professional.objects.filter(
                dni=lookup.validated_data["professional_dni"],
                is_active=True,
                registration_completed_at__isnull=False,
                user__is_active=True,
                user__groups__name=MEDICAL_PROFESSIONAL_GROUP,
            ).first()
            if matched_professional is None:
                error = "No eligible professional matches this DNI."
        else:
            error = lookup.errors["professional_dni"][0]
    if request.method == "POST":
        assignment, _, error = _assign(
            actor_context_from_user(request.user),
            patient,
            request.POST.get("professional_dni", ""),
        )
        if assignment is not None:
            return redirect("patients:care-team", pk=pk)
    assignments = CareRelationship.objects.filter(
        patient=patient, is_active=True
    ).select_related("professional")
    page = Paginator(assignments, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "clinical_records/care_team.html",
        {
            "patient": patient,
            "assignments": page,
            "page_obj": page,
            "error": error,
            "professional_dni": professional_dni,
            "matched_professional": matched_professional,
        },
        status=422 if error and request.method == "POST" else 200,
    )


@administrative_required
@require_http_methods(["GET", "POST"])
def revoke_care(request: HttpRequest, pk: int, relationship_pk: int) -> HttpResponse:
    patient = get_object_or_404(Patient.all_objects, pk=pk)
    assignment = get_object_or_404(
        CareRelationship.objects.select_related("professional"),
        pk=relationship_pk,
        patient=patient,
    )
    error = None
    if request.method == "POST":
        try:
            revoke_care_relationship(
                actor=actor_context_from_user(request.user),
                patient=patient,
                relationship=assignment,
                confirmed=request.POST.get("confirm") == "yes",
            )
        except CareConfirmationRequired as exc:
            error = str(exc)
        else:
            return redirect("patients:care-team", pk=pk)
    return render(
        request,
        "clinical_records/care_revoke.html",
        {
            "patient": patient,
            "assignment": assignment,
            "error": error,
        },
        status=422 if error else 200,
    )


class CareTeamAPIView(GenericAPIView):
    permission_classes = [IsAdministrativeActor]
    serializer_class = CareAssignmentInput

    def get(self, request: Request, pk: int) -> Response:
        patient = get_object_or_404(Patient.all_objects, pk=pk)
        assignments = CareRelationship.objects.filter(
            patient=patient, is_active=True
        ).select_related("professional")
        page = Paginator(assignments, 20).get_page(request.query_params.get("page"))

        def page_url(number):
            return request.build_absolute_uri(
                reverse("patients:api-care-team", args=[pk]) + f"?page={number}"
            )

        return Response(
            {
                "count": page.paginator.count,
                "next": page_url(page.next_page_number()) if page.has_next() else None,
                "previous": page_url(page.previous_page_number())
                if page.has_previous()
                else None,
                "results": [_data(item) for item in page],
            }
        )

    def post(self, request: Request, pk: int) -> Response:
        patient = get_object_or_404(Patient.all_objects, pk=pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            assignment, created = assign_care_relationship(
                actor=actor_context_from_user(request.user),
                patient=patient,
                professional_dni=serializer.validated_data["professional_dni"],
            )
        except ValidationError as error:
            return Response({"professional_dni": error.messages}, status=400)
        return Response(
            _data(assignment),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class CareRevokeAPIView(GenericAPIView):
    permission_classes = [IsAdministrativeActor]
    serializer_class = CareRevokeInput

    def post(self, request: Request, pk: int, relationship_pk: int) -> Response:
        patient = get_object_or_404(Patient.all_objects, pk=pk)
        assignment = get_object_or_404(
            CareRelationship, pk=relationship_pk, patient=patient
        )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = revoke_care_relationship(
            actor=actor_context_from_user(request.user),
            patient=patient,
            relationship=assignment,
            confirmed=True,
        )
        return Response(_data(result))
