from typing import ClassVar

from django.db import migrations

ROLE_GROUPS = (
    "Administrative",
    "Medical Professionals",
)


def create_role_groups(apps, schema_editor):
    group_model = apps.get_model("auth", "Group")
    for group_name in ROLE_GROUPS:
        group_model.objects.get_or_create(name=group_name)


def remove_role_groups(apps, schema_editor):
    group_model = apps.get_model("auth", "Group")
    group_model.objects.filter(name__in=ROLE_GROUPS).delete()


class Migration(migrations.Migration):
    initial = True

    dependencies: ClassVar = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations: ClassVar = [
        migrations.RunPython(create_role_groups, remove_role_groups),
    ]
