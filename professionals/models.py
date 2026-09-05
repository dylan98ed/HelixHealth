from django.conf import settings
from django.db import models


class ActiveReferenceData(models.Model):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Specialty(ActiveReferenceData):
    class Meta(ActiveReferenceData.Meta):
        verbose_name_plural = "specialties"


class HospitalService(ActiveReferenceData):
    pass


class Professional(models.Model):
    """Minimal authenticated professional identity required by HU-03.

    HU-04 extends this model with the professional profile and license fields.
    """

    id = models.BigAutoField(primary_key=True, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="professional_profile",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("id",)

    def __str__(self) -> str:
        return self.user.get_username()
