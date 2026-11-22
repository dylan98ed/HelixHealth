from django.db import migrations


def seed_reception(apps, schema_editor):
    apps.get_model("auth", "Group").objects.get_or_create(name="Reception")


class Migration(migrations.Migration):
    dependencies = [("access_control", "0001_seed_role_groups")]
    operations = [migrations.RunPython(seed_reception, migrations.RunPython.noop)]
