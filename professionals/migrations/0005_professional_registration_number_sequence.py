from django.db import migrations

SEQUENCE_NAME = "professionals_registration_number_seq"


class Migration(migrations.Migration):
    dependencies = [("professionals", "0004_professional_registration_fields")]

    operations = [
        migrations.RunSQL(
            sql=f"CREATE SEQUENCE {SEQUENCE_NAME} START WITH 1 INCREMENT BY 1",
            reverse_sql=f"DROP SEQUENCE {SEQUENCE_NAME}",
        )
    ]
