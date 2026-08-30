from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("patients", "0002_clinical_record_number_sequence")]

    operations = [
        migrations.AlterField(
            model_name="patient",
            name="clinical_record_number",
            field=models.CharField(editable=False, max_length=32, unique=True),
        ),
    ]
