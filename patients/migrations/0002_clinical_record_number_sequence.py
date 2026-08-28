from typing import ClassVar

from django.db import migrations


class Migration(migrations.Migration):
    dependencies: ClassVar = [("patients", "0001_initial")]

    operations: ClassVar = [
        migrations.RunSQL(
            sql=(
                'CREATE SEQUENCE "patients_clinical_record_number_seq" '
                "AS bigint START WITH 1 INCREMENT BY 1 NO CYCLE;"
            ),
            reverse_sql=('DROP SEQUENCE "patients_clinical_record_number_seq";'),
        ),
    ]
