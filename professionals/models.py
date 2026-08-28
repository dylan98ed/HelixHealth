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
