from django.db import migrations, models
from django.db.models import Q

import professionals.validators


class Migration(migrations.Migration):
    dependencies = [("professionals", "0005_professional_registration_number_sequence")]

    operations = [
        migrations.AddField(
            model_name="professional",
            name="license_number",
            field=models.CharField(
                blank=True,
                max_length=50,
                null=True,
                validators=[professionals.validators.validate_license_number],
            ),
        ),
        migrations.AddConstraint(
            model_name="professional",
            constraint=models.CheckConstraint(
                condition=Q(("license_number__isnull", True))
                | Q(("license_number__regex", r".*\S.*")),
                name="professional_license_number_null_or_nonblank",
            ),
        ),
    ]
